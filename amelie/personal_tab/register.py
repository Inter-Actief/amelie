import base64
import io
import json
import uuid
from typing import List
from urllib.parse import urljoin

import qrcode
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.messages import DEFAULT_LEVELS
from django.core.exceptions import ValidationError
from django.db import models
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
from django.utils.translation import gettext_lazy as _l
from django.utils.translation import gettext as _

from amelie import settings
from amelie.members.models import Person
from amelie.personal_tab.models import RFIDCard
from amelie.tools.fields import Char32UUIDField
from amelie.tools.http import HttpJSONResponse


class CardRegistrationIndex(TemplateView):
    template_name = "register/register_card_index.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {})

class RegisterLogoutView(View):
    def get(self, request):
        # Remove any session variables that might be set
        if 'REGISTRATION_TOKEN' in self.request.session:
            del self.request.session['REGISTRATION_TOKEN']
        if 'REGISTER_TAG_ID' in self.request.session:
            del self.request.session['REGISTER_TAG_ID']


        # Check for any messages that were passed by JS as a get parameter
        msg = self.request.GET.get("msg", None)
        if msg is not None:
            msg_type = self.request.GET.get("msg_type", None)
            if msg_type is None:
                msg_type = "INFO"
            messages.add_message(self.request, DEFAULT_LEVELS[msg_type], msg)

        # Redirect to the home page
        return redirect('personal_tab:register_index')

class RegisterProcessRFIDView(View):
    http_method_names = ['post']
    def post(self, request):
        if 'tag' not in request.POST:
            messages.error(request, _l("Something went wrong, please try again later."))
            return redirect('personal_tab:register_logout')

        tag = request.POST['tag']

        if not tag or not isinstance(tag, str):
            messages.error(request, _l("Something went wrong, please try again later."))
            return redirect('personal_tab:register_logout')

        rfid_cards: List[RFIDCard] = list(RFIDCard.objects.filter(code__in=[tag], active=True))
        people = [r.person for r in rfid_cards]

        if people:
            # Found one or more people
            if len(set(people)) == 1:
                person = Person.objects.get(pk=people[0].id)
                card = rfid_cards[0]
                if person.has_mandate_consumptions() and person.is_member():
                    # card.last_used = timezone.now()
                    # card.save()
                    messages.error(request,
                                   _l('This card has already been registered.'))
                    return redirect('personal_tab:register_logout')
                else:
                    messages.error(request,
                                   _l('You do not have a valid mandate or are not a member anymore. Contact the board for help.'))
                    return redirect('personal_tab:register_logout')
            else:
                messages.error(request, _l('RFID-cards from multiple people recognised. Please scan one card at a time.'))
                return redirect('personal_tab:register_logout')
        else:
            request.session['REGISTER_TAG_ID'] = tag
            return redirect('personal_tab:register_generate_qr')



class PendingRegisterToken(models.Model):

    token = Char32UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, blank=True, null=True, related_name='pending_register_login_tokens', on_delete=models.CASCADE)
    created_at = models.DateTimeField(editable=False)

    def save(self, *args, **kwargs):
        '''On create, update creation timestamp'''
        # Override save method because then we use the timezone-aware version of datetime.now()
        # See https://stackoverflow.com/questions/1737017/django-auto-now-and-auto-now-add/1737078#1737078
        if not self.created_at:
            self.created_at = timezone.now()
        return super(PendingRegisterToken, self).save(*args, **kwargs)

    def get_url(self):
        redirect_url = reverse('personal_tab:register_verify', kwargs={'uuid': str(self.token)})
        return urljoin(settings.ABSOLUTE_PATH_TO_SITE, redirect_url)

    def png_image(self):
        qr = qrcode.make(self.get_url())
        img = io.BytesIO()
        qr.save(img)
        img_txt = base64.b64encode(img.getvalue())
        img.close()
        return (bytes("data:image/jpeg;base64,".encode()) + img_txt).decode()


class RegisterGenerateQRView(TemplateView):
    template_name = "pos/show_qr.html"

    def get_context_data(self, **kwargs):
        context = super(RegisterGenerateQRView, self).get_context_data(**kwargs)
        context['type'] = "register"
        context['register_mode'] = True
        context['token'] = PendingRegisterToken.objects.create()
        return context

    def get(self, request, *args, **kwargs):

        token = None
        rfid_card = None

        # If a login token is present, remove it
        if 'REGISTRATION_TOKEN' in request.session:
            # Extract the registration token, set the correct token type and delete the token from the session.
            token = self.request.session['REGISTRATION_TOKEN']
            del self.request.session['REGISTRATION_TOKEN']

        # Check the RFID card that was scanned if it can be registered
        if 'REGISTER_TAG_ID' not in request.session:
            messages.error(request, _l("No card was scanned, please try again."))
            return redirect('personal_tab:register_logout')

        # Extract card ID and remove from session
        rfid_card = request.session['REGISTER_TAG_ID']
        del request.session['REGISTER_TAG_ID']
        if not rfid_card:
            messages.error(request, _l("Something went wrong while scanning the RFID card. Please try again."))
            return redirect('personal_tab:register_logout')

        # Check if card is already registered
        try:
            rfid_card_obj = RFIDCard.objects.get(code=rfid_card)
            if rfid_card_obj.active:
                messages.error(request, _l("This card is already registered."))
            else:
                messages.error(request, _l("This card has already been registered, "
                                          "but has not been activated on the website. "
                                          "Please contact the board."))
            return redirect('personal_tab:register_logout')
        except RFIDCard.DoesNotExist:
            pass  # Card is not yet registered.'

        # If a token was extracted, check if it is valid and used.
        # Remove it if it is valid but not yet used, we will create a new one in the get_context_data method.
        if token is not None:
            try:
                pending_token = PendingRegisterToken.objects.get(token=token)
            except PendingRegisterToken.DoesNotExist:
                # Invalid or expired token, do nothing. The token will be removed and a new token will be generated.
                pending_token = None

            if pending_token is not None and pending_token.user is not None:
                # User has just logged in, check if user has a Person object and is allowed to do stuff.
                # If the user is allowed to do stuff, do the action that the pending token indicates (register/login).
                if not pending_token.user.is_active:
                    messages.error(request, _l("This user is inactive. Please contact the board."))
                    return redirect('personal_tab:register_logout')

                if not hasattr(pending_token.user, 'person'):
                    messages.error(request, _l("You are (not yet/ no longer) a member of Inter-Actief. "
                                              "Ask the board for a membership form."))
                    return redirect('personal_tab:register_logout')

                # User is OK to register card! Register card to person and return to the main screen.
                RFIDCard(person=pending_token.user.person, code=rfid_card, active=True).save()
                messages.success(request, _l("Card successfully registered."))
                return redirect('personal_tab:register_logout')
            elif pending_token is not None:
                # Unused token, delete it anyway, we will create a new one in the get_context_data for safety reasons.
                pending_token.delete()

        # If an RFID card was extracted from the session, re-add it.
        # If something went wrong or the card was registered we should have already been redirected away.
        if rfid_card:
            self.request.session['REGISTER_TAG_ID'] = rfid_card

        return super(RegisterGenerateQRView, self).get(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        # Save registration token and RFID card tag to session
        self.request.session['REGISTRATION_TOKEN'] = str(context['token'].token)
        return super(RegisterGenerateQRView, self).render_to_response(context, **response_kwargs)



class RegisterVerifyTokenView(TemplateView):
    template_name = "pos/verify.html"

    def render_to_response(self, context, **response_kwargs):
        uuid = self.kwargs.get('uuid', None)
        if uuid is None:
            context['message'] = _l("Invalid login token, please try again!")
            context['success'] = False

        # If no user is logged in, redirect to login and then back here.
        if not self.request.user.is_authenticated:
            redirect_url = reverse('personal_tab:register_verify', kwargs={'uuid': uuid})
            login_url_with_redirect = reverse('oidc_authentication_init') + "?next={}".format(redirect_url)
            return redirect(login_url_with_redirect)

        pending_login = None
        try:
            pending_login = PendingRegisterToken.objects.get(token=uuid)
        except PendingRegisterToken.DoesNotExist:
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

            context['message'] = _l("New card registration verified successfully!")
            context['success'] = True

        if 'message' not in context:
            context['message'] = _l("An unknown error occurred, please try again!")
            context['success'] = False

        return super(RegisterVerifyTokenView, self).render_to_response(context, **response_kwargs)


class RegisterCheckLoginAjaxView(View):
    def get(self, request, uuid):
        try:
            pending_login = PendingRegisterToken.objects.get(token=uuid)
        except PendingRegisterToken.DoesNotExist:
            return HttpJSONResponse({
                'message': str(_("The login code is invalid or expired, please try again!")),
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
