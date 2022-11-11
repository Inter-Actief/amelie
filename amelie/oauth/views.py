from django.contrib.auth import login
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.generic import FormView

from amelie.iamailer import MailTask, Recipient
from amelie.members.models import Person
from amelie.oauth.forms import OAuth2RequestForm
from amelie.oauth.models import LoginToken
from amelie.settings import DEFAULT_FROM_EMAIL
from amelie.tools.decorators import require_board
from amelie.tools.mail import PersonRecipient
from django.utils.translation import gettext_lazy as _


def token_login(request, token):
    try:
        deadline = timezone.now() - LoginToken.EXPIRE_AFTER
        token = LoginToken.objects.get(token=token, date__gte=deadline)
    except LoginToken.DoesNotExist:
        return render(request=request,
                      template_name="403.html",
                      context={'reason': _('The login token does not exist or is expired.')},
                      status=403)
    else:
        if token.person.user is None:
            return render(request=request,
                          template_name="403.html",
                          context={'reason': _('Your account is currently not linked to a user. '
                                               'Please contact the board.')},
                          status=403)
        login(request, token.person.user, backend="amelie.tools.auth.IALoginBackend")
        token.delete()

        return render(request, 'token_login.html', {})


def create_token_and_send_email(request, person):
    token = LoginToken()
    token.person = person
    token.save()

    url = request.build_absolute_uri(token.get_absolute_url())

    task = MailTask(template_name="send_token.mail",
                    report_to=request.person.email_address,
                    report_always=False)

    task.add_recipient(PersonRecipient(
        recipient=person,
        context={"url": url}
    ))

    task.send()


@require_board
def send_token(request, person_id):
    person = get_object_or_404(Person, id=person_id)
    create_token_and_send_email(request, person)
    return HttpResponse(_("Sent"))


class RequestOAuth(FormView):
    template_name = "request_oauth.html"
    form_class = OAuth2RequestForm

    def form_valid(self, form):
        application_name = form.cleaned_data['application_name']
        member_name = form.cleaned_data['member_name']
        member_mail = form.cleaned_data['member_mail']
        redirect_urls = form.cleaned_data['redirect_urls']
        client_type = form.cleaned_data['client_type']
        description = form.cleaned_data['description']

        # Each redirect URL is located on a new line. Transform these into a list.
        redirect_urls_list = redirect_urls.split("\r\n")

        # Send message to WWW
        context = {
            'application_name': application_name,
            'member_name': member_name,
            'member_mail': member_mail,
            'redirect_urls': redirect_urls_list,
            'client_type': client_type,
            'description': description
        }
        task = MailTask(
            from_=DEFAULT_FROM_EMAIL,
            template_name='oauth_access_request.mail')
        task.add_recipient(Recipient(
            tos=['WWW Supers <www-super@inter-actief.net>'],
            context=context
        ))
        task.send(delay=False)

        return render(self.request, 'request_oauth_sent.html', context)
