from django.urls import path

from amelie.claudia.account_views import AccountHome, AccountActivate, AccountActivateSuccess, AccountPassword, \
    AccountPasswordSuccess, AccountConfigureForwardingView, AccountCheckForwardingVerificationStatus, \
    AccountAddForwardingAddress, AccountActivateForwardingAddress, AccountDeactivateForwardingAddress, \
    AccountPasswordReset, AccountPasswordResetSuccess, AccountPasswordResetLink, AccountCheckForwardingStatus, \
    MailAliasView, KanidmActions, KanidmSudoReset

app_name = 'account'

urlpatterns = [
    path('', AccountHome.as_view(), name='home'),

    path('server/update/', KanidmActions.as_view(), name='server_update'),
    path('server/sudo_reset/<str:reset_code>/', KanidmSudoReset.as_view(), name='server_sudo_reset'),

    path('activate/', AccountActivate.as_view(), name='activate'),
    path('activate/success/', AccountActivateSuccess.as_view(), name='activate_success'),
    path('password/', AccountPassword.as_view(), name='password'),
    path('password/success/', AccountPasswordSuccess.as_view(), name='password_success'),
    path('password/reset/', AccountPasswordReset.as_view(), name='password_reset'),
    path('password/reset/success/', AccountPasswordResetSuccess.as_view(), name='password_reset_success'),
    path('password/reset/<str:reset_code>/', AccountPasswordResetLink.as_view(), name='password_reset_link'),

    path('email_forwarding/', AccountConfigureForwardingView.as_view(), name='configure_forwarding'),
    path('email_forwarding/status/', AccountCheckForwardingStatus.as_view(), name='check_forwarding_status'),
    path('email_forwarding/check/', AccountCheckForwardingVerificationStatus.as_view(), name='check_forwarding_verification'),
    path('email_forwarding/add/', AccountAddForwardingAddress.as_view(), name='add_forwarding_address'),
    path('email_forwarding/activate/', AccountActivateForwardingAddress.as_view(), name='activate_forwarding_address'),
    path('email_forwarding/deactivate/', AccountDeactivateForwardingAddress.as_view(), name='deactivate_forwarding_address'),

    path('mail_alias/', MailAliasView.as_view(), name='mail_alias'),
]

# vim:set sw=4 sts=4 ts=4 et si:
