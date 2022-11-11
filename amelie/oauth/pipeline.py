from django.contrib import messages
from django.urls import reverse
from django.utils.http import urlencode
from social_core.pipeline.partial import partial
from django.utils.translation import gettext_lazy as _

from amelie.oauth.templatetags.provider_name import provider_name


@partial
def require_login_for_association(strategy, current_partial, user=None, *args, **kwargs):
    if user is not None:
        return

    # Instruct the login view not to offer an oauth login option.
    # Set the next link to resume the social_oauth pipeline, associating the user.
    continue_url = reverse('social_auth:complete', kwargs={"backend": current_partial.backend})

    query = {
        'no_oauth': '1',
        'next': continue_url,
    }

    return strategy.redirect(reverse('login') + '?' + urlencode(query))


def message_new_association(request, backend=None, new_association=False, *args, **kwargs):
    if new_association:
        message = _("Login provider %(provider)s added successfully") % {'provider': provider_name(backend)}
        messages.success(request, message)


def message_remove_association(strategy=None, backend=None, *args, **kwargs):
    message = _("Login provider %(provider)s has been deleted") % {'provider': provider_name(backend)}
    messages.success(strategy.request, message)
