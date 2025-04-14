import json
import logging
import operator
from functools import reduce
from typing import List

from django.conf import settings
from django.contrib import messages
from django.contrib.messages import DEFAULT_LEVELS
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView, FormView
from django.utils.translation import gettext_lazy as _l
from django.utils.translation import gettext as _

from amelie.activities.models import Activity
from amelie.members.models import Person
from amelie.personal_tab.forms import CookieCornerPersonSearchForm
from amelie.personal_tab.models import RFIDCard, Category, CookieCornerTransaction, Article
from amelie.personal_tab.pos_models import PendingPosToken
from amelie.personal_tab.transactions import free_cookie_is_winner, free_cookies_allowed, free_cookies_sale, \
    cookie_corner_sale
from amelie.tools.decorators import request_passes_test
from amelie.tools.http import HttpJSONResponse, get_client_ips
from amelie.tools.mixins import RequireCookieCornerMixin


def require_cookie_corner_pos(func):
    if settings.DEBUG:
        return func
    else:
        def is_cookie_corner_ip(request):
            all_ips, real_ip = get_client_ips(request)
            access_allowed = real_ip in settings.COOKIE_CORNER_POS_IP_ALLOWLIST or request.user.is_superuser
            if not access_allowed:
                logger = logging.getLogger("amelie.personal_tab.pos_views.require_cookie_corner_pos")
                logger.warning(f"Client with IP '{real_ip}' was denied access to cookie corner. Not on allowlist. Possible (unchecked) other IPs: {all_ips}")
            return access_allowed
        return request_passes_test(
            is_cookie_corner_ip,
            reden=_l('Access for personal tab only.')
        )(func)


class PosHomeView(RequireCookieCornerMixin, TemplateView):
    template_name = "pos/home.html"

    def get_context_data(self, **kwargs):
        context = super(PosHomeView, self).get_context_data(**kwargs)
        context['upcoming_activities'] = Activity.objects.filter(begin__gte=timezone.now())[:5]
        context['past_activities'] = Activity.objects.distinct().filter(begin__lt=timezone.now(), photos__gt=0,
                                                                        photos__public=True).order_by('-begin')[:8]
        return context

    def render_to_response(self, context, **response_kwargs):
        # Remove any session variables that might be set
        if 'POS_REGISTRATION_TOKEN' in self.request.session:
            del self.request.session['POS_REGISTRATION_TOKEN']
        if 'POS_REGISTER_TAG_ID' in self.request.session:
            del self.request.session['POS_REGISTER_TAG_ID']
        if 'POS_LOGIN_TOKEN' in self.request.session:
            del self.request.session['POS_LOGIN_TOKEN']
        if 'POS_LOGIN_UID' in self.request.session:
            del self.request.session['POS_LOGIN_UID']

        return super(PosHomeView, self).render_to_response(context, **response_kwargs)


class PosProcessRFIDView(RequireCookieCornerMixin, View):
    http_method_names = ['post']
    def post(self, request):
        if 'tags' not in request.POST:
            messages.error(request, _l("Something went wrong, please try again later."))
            return redirect('personal_tab:pos_logout')

        tags = json.loads(request.POST['tags'])

        if not tags:
            messages.error(request, _l('No cards were scanned, please try again.'))
            return redirect('personal_tab:pos_logout')

        rfid_cards: List[RFIDCard] = list(RFIDCard.objects.filter(code__in=tags, active=True))
        people = [r.person for r in rfid_cards]

        if people:
            # Found one or more people
            if len(set(people)) == 1:
                person = Person.objects.get(pk=people[0].id)
                card = rfid_cards[0]
                if person.has_mandate_consumptions() and person.is_member():
                    # Found one person, set username to session, update last used time on RFID and continue to shop
                    self.request.session['POS_LOGIN_UID'] = people[0].id
                    card.last_used = timezone.now()
                    card.save()
                    return redirect("personal_tab:pos_shop")
                else:
                    messages.error(request,
                                   _l('You do not have a valid mandate or are not a member anymore. Contact the board for help.'))
                    return redirect('personal_tab:pos_logout')
            else:
                messages.error(request, _l('RFID-cards from multiple people recognised. Please scan one card at a time.'))
                return redirect('personal_tab:pos_logout')
        else:
            if len(tags) == 1:
                request.session['POS_REGISTER_TAG_ID'] = tags[0]
                return redirect('personal_tab:pos_generate_qr', type="register")
            else:
                messages.error(request, _l('Multiple unknown RFID-cards detected. Please scan one card at a time.'))
                return redirect('personal_tab:pos_logout')


class PosGenerateQRView(RequireCookieCornerMixin, TemplateView):
    template_name = "pos/show_qr.html"

    def get_context_data(self, **kwargs):
        context = super(PosGenerateQRView, self).get_context_data(**kwargs)
        qr_type = kwargs.get('type', None)
        context['type'] = qr_type
        if qr_type is not None and qr_type == 'login':
            # Create new login token
            context['token'] = PendingPosToken.objects.create(type=PendingPosToken.TokenTypes.LOGIN)
        elif qr_type is not None and qr_type == 'register':
            # Create new registration token
            context['token'] = PendingPosToken.objects.create(type=PendingPosToken.TokenTypes.REGISTRATION)
        else:
            raise ValueError(_l("Invalid token type requested."))
        return context

    def get(self, request, *args, **kwargs):
        qr_type = kwargs.get('type', None)

        # If type is invalid, raise an error
        if qr_type is None or qr_type not in ['login', 'register']:
            raise ValueError(_l("Invalid token type requested!"))

        # If someone was logged in, he's not any more!
        if 'POS_LOGIN_UID' in self.request.session:
            del self.request.session['POS_LOGIN_UID']

        token = None
        token_type = None
        rfid_card = None
        if qr_type == 'login':
            # If a registration token is present, remove it
            if 'POS_REGISTRATION_TOKEN' in request.session:
                del self.request.session['POS_REGISTRATION_TOKEN']
            if 'POS_LOGIN_TOKEN' in request.session:
                # Extract the login token, set the correct token type and delete the token from the session.
                token = self.request.session['POS_LOGIN_TOKEN']
                token_type = PendingPosToken.TokenTypes.LOGIN
                del self.request.session['POS_LOGIN_TOKEN']
        elif qr_type == 'register':
            # If a login token is present, remove it
            if 'POS_LOGIN_TOKEN' in request.session:
                del self.request.session['POS_LOGIN_TOKEN']
            if 'POS_REGISTRATION_TOKEN' in request.session:
                # Extract the registration token, set the correct token type and delete the token from the session.
                token = self.request.session['POS_REGISTRATION_TOKEN']
                token_type = PendingPosToken.TokenTypes.REGISTRATION
                del self.request.session['POS_REGISTRATION_TOKEN']

            # Check the RFID card that was scanned if it can be registered
            if 'POS_REGISTER_TAG_ID' not in request.session:
                messages.error(request, _l("No card was scanned, please try again."))
                return redirect('personal_tab:pos_logout')

            # Extract card ID and remove from session
            rfid_card = request.session['POS_REGISTER_TAG_ID']
            del request.session['POS_REGISTER_TAG_ID']
            if not rfid_card:
                messages.error(request, _l("Something went wrong while scanning the RFID card. Please try again."))
                return redirect('personal_tab:pos_logout')

            # Check if card is already registered
            try:
                rfid_card_obj = RFIDCard.objects.get(code=rfid_card)
                if rfid_card_obj.active:
                    messages.error(request, _l("This card is already registered."))
                else:
                    messages.error(request, _l("This card has already been registered, "
                                              "but has not been activated on the website. "
                                              "Please contact the board."))
                return redirect('personal_tab:pos_logout')
            except RFIDCard.DoesNotExist:
                pass  # Card is not yet registered.'

        # If a token was extracted, check if it is valid and used.
        # Remove it if it is valid but not yet used, we will create a new one in the get_context_data method.
        if token is not None:
            try:
                pending_token = PendingPosToken.objects.get(type=token_type, token=token)
            except PendingPosToken.DoesNotExist:
                # Invalid or expired token, do nothing. The token will be removed and a new token will be generated.
                pending_token = None

            if pending_token is not None and pending_token.user is not None:
                # User has just logged in, check if user has a Person object and is allowed to do stuff.
                # If the user is allowed to do stuff, do the action that the pending token indicates (register/login).
                if not pending_token.user.is_active:
                    messages.error(request, _l("This user is inactive. Please contact the board."))
                    return redirect('personal_tab:pos_logout')

                if not hasattr(pending_token.user, 'person'):
                    messages.error(request, _l("You are (not yet/ no longer) a member of Inter-Actief. "
                                              "Ask the board for a membership form."))
                    return redirect('personal_tab:pos_logout')

                if pending_token.type == PendingPosToken.TokenTypes.LOGIN:
                    # User is OK to buy stuff! Set person ID to session, delete token and continue to the shop.
                    self.request.session['POS_LOGIN_UID'] = pending_token.user.person.id
                    pending_token.delete()
                    return redirect('personal_tab:pos_shop')
                elif pending_token.type == PendingPosToken.TokenTypes.REGISTRATION:
                    # User is OK to register card! Register card to person and return to the main screen.
                    RFIDCard(person=pending_token.user.person, code=rfid_card, active=True).save()
                    messages.success(request, _l("Card successfully registered. Please scan the card again to log in."))
                    return redirect('personal_tab:pos_logout')
            elif pending_token is not None:
                # Unused token, delete it anyway, we will create a new one in the get_context_data for safety reasons.
                pending_token.delete()

        # If an RFID card was extracted from the session, re-add it.
        # If something went wrong or the card was registered we should have already been redirected away.
        if rfid_card:
            self.request.session['POS_REGISTER_TAG_ID'] = rfid_card

        return super(PosGenerateQRView, self).get(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        qr_type = self.kwargs.get("type", None)
        if qr_type is not None and qr_type == "login":
            # Save login token to session
            self.request.session['POS_LOGIN_TOKEN'] = str(context['token'].token)
        elif qr_type is not None and qr_type == "register":
            # Save registration token and RFID card tag to session
            self.request.session['POS_REGISTRATION_TOKEN'] = str(context['token'].token)
        else:
            raise ValueError(_l("Invalid token type requested."))

        return super(PosGenerateQRView, self).render_to_response(context, **response_kwargs)


class PosVerifyTokenView(TemplateView):
    template_name = "pos/verify.html"

    def render_to_response(self, context, **response_kwargs):
        uuid = self.kwargs.get('uuid', None)
        if uuid is None:
            context['message'] = _l("Invalid login token, please try again!")
            context['success'] = False

        # If no user is logged in, redirect to login and then back here.
        if not self.request.user.is_authenticated:
            redirect_url = reverse('personal_tab:pos_verify', kwargs={'uuid': uuid})
            login_url_with_redirect = reverse('oidc_authentication_init') + "?next={}".format(redirect_url)
            return redirect(login_url_with_redirect)

        pending_login = None
        try:
            pending_login = PendingPosToken.objects.get(token=uuid)
        except PendingPosToken.DoesNotExist:
            context['message'] = _l("Invalid token, please try again!")
            context['success'] = False
        except ValidationError:
            context['message'] = _l("Invalid token, please try again!")
            context['success'] = False

        if pending_login is not None and pending_login.user is not None:
            context['message'] = _l("This token was already used before, please try again!")
            context['success'] = False
        elif pending_login is not None:
            pending_login.user = self.request.user
            pending_login.save()
            if pending_login.type == PendingPosToken.TokenTypes.LOGIN:
                context['message'] = _l("Cookie Corner login verified successfully!")
            elif pending_login.type == PendingPosToken.TokenTypes.REGISTRATION:
                context['message'] = _l("New card registration verified successfully!")
            else:
                context['message'] = _l("Unknown token verified successfully!")
            context['success'] = True

        if 'message' not in context:
            context['message'] = _l("An unknown error occurred, please try again!")
            context['success'] = False

        return super(PosVerifyTokenView, self).render_to_response(context, **response_kwargs)


class PosCheckLoginAjaxView(RequireCookieCornerMixin, View):
    def get(self, request, uuid):
        try:
            pending_login = PendingPosToken.objects.get(token=uuid)
        except PendingPosToken.DoesNotExist:
            return HttpJSONResponse({
                'message': str(_("The login code is invalid or expired, please try again!.")),
                'status': False,
                'error': True,
            })

        if pending_login.user is None:
            return HttpJSONResponse({
                'message': "",
                'status': False,
                'error': False,
            })
        else:
            return HttpJSONResponse({
                'message': "",
                'status': True,
                'error': False,
            })


class PosLogoutView(RequireCookieCornerMixin, View):
    def get(self, request):
        # Remove any session variables that might be set
        if 'POS_REGISTRATION_TOKEN' in self.request.session:
            del self.request.session['POS_REGISTRATION_TOKEN']
        if 'POS_REGISTER_TAG_ID' in self.request.session:
            del self.request.session['POS_REGISTER_TAG_ID']
        if 'POS_LOGIN_TOKEN' in self.request.session:
            del self.request.session['POS_LOGIN_TOKEN']
        if 'POS_LOGIN_UID' in self.request.session:
            del self.request.session['POS_LOGIN_UID']

        # Check for any messages that were passed by JS as a get parameter
        msg = self.request.GET.get("msg", None)
        if msg is not None:
            msg_type = self.request.GET.get("msg_type", None)
            if msg_type is None:
                msg_type = "INFO"
            messages.add_message(self.request, DEFAULT_LEVELS[msg_type], msg)

        # Check if any preset messages are requested by JS
        msg_preset = self.request.GET.get("msg_preset", None)
        if msg_preset is not None:
            if msg_preset == "timeout":
                messages.info(request, _l("Session timed out. You were logged out."))
            elif msg_preset == "cancelled":
                messages.info(request, _l("Purchase cancelled. You are now logged out."))

        # Redirect to the home page
        return redirect('personal_tab:pos_index')


class PosShopView(RequireCookieCornerMixin, TemplateView):
    template_name = "pos/shop.html"
    http_method_names = ['get', 'post']

    def get_context_data(self, **kwargs):
        context = super(PosShopView, self).get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(is_available=True).order_by('order').prefetch_related('article_set')

        # Get person
        if 'POS_LOGIN_UID' in self.request.session:
            pid = self.request.session['POS_LOGIN_UID']
            person = Person.objects.get(id=pid)
            context['pos_person'] = person
            del self.request.session['POS_LOGIN_UID']

            # Get person's top 5 products
            # We're doing this in python, because we only want to use the last 100 transactions for the top 5.
            last_transactions = CookieCornerTransaction.objects.filter(person=person, article__is_available=True).exclude(
                article__category__show_calculator_in_pos=True
            )[:100]

            favourites = {}
            for trans in last_transactions:
                if trans.article_id not in favourites:
                    favourites[trans.article_id] = 0
                favourites[trans.article_id] += trans.amount

            # Now we'll just sort it by value.
            favourites = sorted(favourites.items(), key=operator.itemgetter(1))

            sorted_favourites = []
            for fav in favourites[:-6:-1]:  # These are the last 5 in reverse order
                article = Article.objects.get(id=fav[0])
                sorted_favourites.append({
                    "id": article.id,
                    "name": article.name,
                    "price": str(article.price).replace(".", ","),
                    "article_image": article.image.url if article.image else None,
                    "amount": fav[1],
                })
            context['top_five_products'] = sorted_favourites

        return context

    def post(self, request):
        person = None
        if 'POS_LOGIN_UID' in request.session:
            try:
                person = Person.objects.get(id=request.session['POS_LOGIN_UID'])
            except Person.DoesNotExist:
                pass
            del request.session['POS_LOGIN_UID']

        if person is None:
            messages.error(request, _l("No user was logged in. No products were purchased, please try again."))
            return redirect("personal_tab:pos_logout")

        if 'cart' not in request.POST:
            messages.error(request, _l("Invalid shopping cart. No products are bought. Please try again. (error 1)"))
            return redirect("personal_tab:pos_logout")

        cart = json.loads(request.POST['cart'])
        transactions = []
        total_price = 0
        total_kcal = 0

        # Free cookie action
        is_winner = free_cookie_is_winner(person)
        action_processed = False

        if not cart:
            messages.error(request, _l("No products were selected. Please try again."))
            return redirect("personal_tab:pos_logout")

        for i in cart:
            if 'product' not in i or 'amount' not in i:
                messages.error(request, _l("Invalid shopping cart. No products are bought. Please try again. (error 2)"))
                return redirect("personal_tab:pos_logout")

            try:
                item = Article.objects.get(id=i['product'])
            except Article.DoesNotExist:
                messages.error(request, _l("Invalid shopping cart. No products are bought. Please try again. (error 3)"))
                return redirect("personal_tab:pos_logout")

            if not item.is_available:
                messages.error(request, _l("Invalid shopping cart. No products are bought. Please try again. (error 4)"))
                return redirect("personal_tab:pos_logout")

            amount = i['amount']

            if is_winner and not action_processed and free_cookies_allowed(item):
                action_processed = True
                cc_transaction = free_cookies_sale(article=item, amount=amount, person=person, added_by=person)
            else:
                cc_transaction = cookie_corner_sale(article=item, amount=amount, person=person, added_by=person)

            total_price += cc_transaction.price
            total_kcal += cc_transaction.kcal() or 0

            transactions.append({
                'item': item,
                'amount': amount,
                'discount': cc_transaction.discount if hasattr(cc_transaction, 'discount') else None,
                'total': cc_transaction.price,
                'subtotal_kcal': cc_transaction.kcal()
            })

        free_cookie_winner = is_winner and action_processed
        has_discount = reduce(lambda x, y: x or y, [bool(t['discount']) for t in transactions])

        return render(request, 'pos/success.html', {
            'success_text': _l('Purchase registered!'),
            'transactions': transactions,
            'discount': has_discount,
            'free_cookie_winner': free_cookie_winner,
            'total_price': total_price,
            'total_kcal': total_kcal
        })

    def render_to_response(self, context, **response_kwargs):
        # Remove any login/registration tokens that might be set
        if 'POS_REGISTRATION_TOKEN' in self.request.session:
            del self.request.session['POS_REGISTRATION_TOKEN']
        if 'POS_REGISTER_TAG_ID' in self.request.session:
            del self.request.session['POS_REGISTER_TAG_ID']
        if 'POS_LOGIN_TOKEN' in self.request.session:
            del self.request.session['POS_LOGIN_TOKEN']

        if 'pos_person' not in context:
            # No person was detected, redirect to login screen
            messages.error(self.request, _l("You have been logged out. No purchase was made. Please try again"))
            return redirect("personal_tab:pos_logout")

        # Keep the user logged in
        self.request.session['POS_LOGIN_UID'] = context['pos_person'].pk

        return super(PosShopView, self).render_to_response(context, **response_kwargs)


class PosRegisterExternalCardView(RequireCookieCornerMixin, FormView):
    template_name = "pos/register_external_card.html"
    success_url = reverse_lazy("personal_tab:pos_logout")
    form_class = CookieCornerPersonSearchForm

    def get_context_data(self, **kwargs):
        context = super(PosRegisterExternalCardView, self).get_context_data(**kwargs)

        # Get person
        if 'POS_LOGIN_UID' in self.request.session:
            pid = self.request.session['POS_LOGIN_UID']
            person = Person.objects.get(id=pid)
            context['pos_person'] = person
            del self.request.session['POS_LOGIN_UID']

        return context

    def form_valid(self, form):
        # Get the person object that we are registering the card to
        try:
            rfid_person = Person.objects.get(id=form.cleaned_data['person'])
        except Person.DoesNotExist:
            # ERROR: Person does not exist
            messages.error(self.request, _l("Selected user does not exist, please try again."))
            return redirect("personal_tab:pos_logout")

        user = rfid_person.user

        if user is None or user.is_active is False:
            # ERROR: User does not exist or is inactive
            messages.error(self.request, _l("This person is (not) a member of Inter-Actief (anymore)."))
            return redirect("personal_tab:pos_logout")

        if not hasattr(user, 'person'):
            # ERROR: User is no member of IA (any more)
            messages.error(self.request, _l("This person is (not) a member of Inter-Actief (anymore)."))
            return redirect("personal_tab:pos_logout")

        # Go to the card scan step
        self.request.session['POS_RFID_PERSON_ID'] = rfid_person.id

        # Continue with scanning the card.
        return redirect('personal_tab:pos_scan_external')

    def get(self, request, *args, **kwargs):
        # Remove any login/registration tokens that might be set
        if 'POS_REGISTRATION_TOKEN' in self.request.session:
            del request.session['POS_REGISTRATION_TOKEN']
        if 'POS_REGISTER_TAG_ID' in self.request.session:
            del request.session['POS_REGISTER_TAG_ID']
        if 'POS_LOGIN_TOKEN' in self.request.session:
            del request.session['POS_LOGIN_TOKEN']

        context = self.get_context_data()

        if 'pos_person' not in context:
            # No person was detected, redirect to login screen
            messages.error(request, _l("You have been logged out. No purchase was made. Please try again"))
            return redirect("personal_tab:pos_logout")

        if not context['pos_person'].is_board() and not context['pos_person'].user.is_superuser:
            messages.error(request, _l('You are not a board member of Inter-Actief. '
                                         'Ask the board to register your card.'))
            return redirect("personal_tab:pos_logout")

        request.session['POS_LOGIN_UID'] = context['pos_person'].pk
        return self.render_to_response(context)


class PosScanExternalCardView(RequireCookieCornerMixin, TemplateView):
    template_name = "pos/scan_external_card.html"
    http_method_names = ['get', 'post']

    def get(self, request, *args, **kwargs):
        # Remove any login/registration tokens that might be set
        if 'POS_REGISTRATION_TOKEN' in self.request.session:
            del request.session['POS_REGISTRATION_TOKEN']
        if 'POS_REGISTER_TAG_ID' in self.request.session:
            del request.session['POS_REGISTER_TAG_ID']
        if 'POS_LOGIN_TOKEN' in self.request.session:
            del request.session['POS_LOGIN_TOKEN']

        if 'POS_LOGIN_UID' not in request.session:
            # No person was detected, redirect to login screen
            messages.error(request, _l("You have been logged out. No card was registered. Please try again"))
            return redirect("personal_tab:pos_logout")

        return self.render_to_response({})

    def post(self, request):
        if 'tags' not in request.POST:
            messages.error(request, _l("Something went wrong, please try again later."))
            return redirect('personal_tab:pos_logout')

        # Get person
        person = None
        if 'POS_RFID_PERSON_ID' in self.request.session:
            pid = self.request.session['POS_RFID_PERSON_ID']
            person = Person.objects.get(id=pid)
            del self.request.session['POS_RFID_PERSON_ID']

        if not person:
            messages.error(request, _l('Something went wrong, please try again later.'))
            return redirect('personal_tab:pos_logout')

        tags = json.loads(request.POST['tags'])

        if not tags:
            messages.error(request, _l('No cards were scanned, please try again.'))
            return redirect('personal_tab:pos_logout')

        people = [r.person for r in RFIDCard.objects.filter(code__in=tags, active=True)]

        if people:
            # Card is already registered to one or more people
            messages.error(request, _l('This card is already registered.'))
            return redirect('personal_tab:pos_logout')
        else:
            if len(tags) == 1:
                # User is OK to register card! Register card to person and return to the main screen.
                RFIDCard(person=person, code=tags[0], active=True).save()
                messages.success(request, _l("Card successfully registered. You have been logged out."))
                return redirect('personal_tab:pos_logout')

            else:
                messages.error(request, _l('Multiple unknown RFID-cards detected. Please scan one card at a time. You have been logged out.'))
                return redirect('personal_tab:pos_logout')
