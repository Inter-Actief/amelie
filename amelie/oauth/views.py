from django.shortcuts import render
from django.views.generic import FormView

from amelie.iamailer import MailTask, Recipient
from amelie.oauth.forms import OAuth2RequestForm
from amelie.settings import DEFAULT_FROM_EMAIL

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
        task.send()

        return render(self.request, 'request_oauth_sent.html', context)
