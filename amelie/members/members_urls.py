from django.urls import path
from django.views.decorators.cache import cache_page
from django.views.generic import RedirectView

from amelie.members import ajax_views, query_views, views
from amelie.members.views import PaymentDeleteView

urlpatterns = [
    path('', query_views.query, name='query'),

    path('mailing/', query_views.send_mailing, name='send_mailing'),
    path('push/', query_views.SendNotification.as_view(), name='send_push'),
    path('data_export/', query_views.DataExport.as_view(), name='data_export'),
    path('statistics/payments/', views.payment_statistics, name='statistics_payments'),
    path('statistics/', views.statistics, name='statistics'),
    path('<int:id>/<slug:slug>/', views.person_view, name='person_view'),
    path('<int:id>/<slug:slug>/edit/', views.person_edit, name='person_edit'),
    path('<int:id>/<slug:slug>/anonymize/', views.person_anonymize, name='person_anonymize'),
    path('<int:id>/<slug:slug>/picture/', views.person_picture, name='person_picture'),
    path('<int:id>/<slug:slug>/person_unverified_picture/', views.person_unverified_picture, name='person_unverified_picture'),
    path('<int:id>/ajax/employee/', ajax_views.person_employee, name='person_employee'),
    path('<int:id>/ajax/preferences/', ajax_views.person_preferences, name='person_preferences'),
    path('<int:id>/ajax/study/', ajax_views.person_study, name='person_study'),
    path('<int:id>/ajax/membership/payments/<int:membership>/', ajax_views.person_payments, name='person_pay'),
    path('<int:id>/ajax/membership/', ajax_views.person_membership, name='person_membership'),
    path('<int:id>/ajax/membership/new/', ajax_views.person_membership_new, name='person_membership_new'),
    path('<int:id>/ajax/membership/end/', ajax_views.person_membership_end, name='person_membership_end'),
    path('<int:person_id>/ajax/membership/sign/<int:membership_id>/', ajax_views.MembershipSignatureView.as_view(), name='person_membership_sign'),
    path('<int:person_id>/ajax/membership/retrieve_signed/<int:membership_id>/', ajax_views.MembershipRetrieveSignedDocumentView.as_view(), name='person_membership_retrieve_signed'),
    path('<int:id>/ajax/membership/<str:option>/', ajax_views.person_membership, name='person_membership'),
    path('<int:id>/ajax/mandate/', ajax_views.person_mandate, name='person_mandate'),
    path('<int:id>/ajax/mandate/new/', ajax_views.person_mandate_new, name='person_mandate_new'),
    path('<int:id>/ajax/mandate/activate/<int:mandate>/', ajax_views.person_mandate_activate, name='person_mandate_activate'),
    path('<int:id>/ajax/mandate/end/<int:mandate>/', ajax_views.person_mandate_end, name='person_mandate_end'),
    path('<int:person_id>/ajax/mandate/sign/<int:mandate_id>/', ajax_views.MandateSignatureView.as_view(), name='person_mandate_sign'),
    path('<int:person_id>/ajax/mandate/retrieve_signed/<int:mandate_id>/', ajax_views.MandateRetrieveSignedDocumentView.as_view(), name='person_mandate_retrieve_signed'),

    path('<int:id>/ajax/functions/', ajax_views.person_functions, name='person_functions'),

    path('ajax/autocomplete/name/', ajax_views.autocomplete_names, name='autocomplete'),
    path('ajax/autocomplete/cookie_corner/name/', ajax_views.autocomplete_names_cookie_corner, name='autocomplete_cookie_corner'),

    path('userinfo/', views.person_userinfo, name='person_userinfo'),
    path('groupinfo/', views.person_groupinfo, name='person_groupinfo'),
    path('send_link_code/<int:person_id>/', views.person_send_link_code, name='send_oauth_link_code'),

    path('payment/<int:pk>/delete/', PaymentDeleteView.as_view(), name='payment_delete'),

    path('birthdays/', views.birthdays, name='birthdays'),

    path('new/general/', views.RegisterNewGeneralWizardView.as_view(), name='person_new_general'),
    path('new/external/', views.RegisterNewExternalWizardView.as_view(), name='person_new_external'),
    path('new/employee/', views.RegisterNewEmployeeWizardView.as_view(), name='person_new_employee'),
    path('new/freshman/', views.RegisterNewFreshmanWizardView.as_view(), name='person_new_freshman'),
    path('preregister/freshman/', views.PreRegisterNewFreshmanWizardView.as_view(), name='person_preregister_freshman'),
    path('preregister/complete/', views.PreRegistrationCompleteView.as_view(), name='person_preregister_complete'),
    path('preregistration/', views.PreRegistrationStatus.as_view(), name='preregistration_status'),
    path('preregistration/print/', views.PreRegistrationPrintAll.as_view(), name='preregistration_print_all'),
    path('preregistration/print/dogroup/', views.PreRegistrationPrintDogroup.as_view(), name='preregistration_print_dogroup'),

    path('registration_form/<int:user>/<int:membership>/', views.registration_form, name='registration_form'),
    path('membership_form/<int:user>/<int:membership>/', views.membership_form, name='membership_form'),
    path('mandate_form/<int:mandate>/', views.mandate_form, name='mandate_form'),

    path('membership_form/signed/<int:person_id>/<int:membership_id>/', views.membership_signed_form, name='membership_signed_form'),
    path('mandate_form/signed/<int:mandate_id>/', views.mandate_signed_form, name='mandate_signed_form'),

    path('registration_check/', views.registration_check, name='registration_check'),
    path('registration_check/<int:id>/<slug:slug>/', views.registration_check_view, name='registration_check_view'),

    path('contact_list/', views.contact_list, name='contact_list'),
    path('export_csv/primary/', views.csv_student_number_primary, name='csv_studentnumber_primary'),
    path('export_csv/withoutbit/', views.csv_student_number_without_bit, name='csv_studentnumber_withoutbit'),

    path('dogroups/', views.DoGroupTreeView.as_view(), name='dogroups'),
    path('dogroups/data/', cache_page(60 * 60 * 24 * 30)(views.DoGroupTreeViewData.as_view()), name='dogroups_data'),

    path('books_list/', views.books_list, name='books_list'),


    # Old (dutch) URLs to not break permalinks
    path('statistieken/betalingen/', RedirectView.as_view(pattern_name='members:statistics_payments', permanent=True)),
    path('statistieken/', RedirectView.as_view(pattern_name='members:statistics', permanent=True)),
    path('<int:id>/<slug:slug>/pasfoto/', RedirectView.as_view(pattern_name='members:person_picture', permanent=True)),
    path('verjaardagen/', RedirectView.as_view(pattern_name='members:birthdays', permanent=True)),
    path('telefoonlijst/', RedirectView.as_view(pattern_name='members:contact_list', permanent=True)),
]
