from django.urls import path
from django.views.decorators.cache import cache_page
from django.views.generic import RedirectView

from amelie.members import ajax_views, query_views, views
from amelie.members.views import PaymentDeleteView

urlpatterns = [

    path(r'', query_views.query, name='query'),

    path(r'mailing/', query_views.send_mailing, name='send_mailing'),
    path(r'push/', query_views.SendNotification.as_view(), name='send_push'),
    path(r'data_export/', query_views.DataExport.as_view(), name='data_export'),
    path(r'statistics/payments/', views.payment_statistics, name='statistics_payments'),
    path(r'statistics/', views.statistics, name='statistics'),
    path(r'<int:id>/<slug:slug>/', views.person_view, name='person_view'),
    path(r'<int:id>/<slug:slug>/edit/', views.person_edit, name='person_edit'),
    path(r'<int:id>/<slug:slug>/anonymize/', views.person_anonymize, name='person_anonymize'),
    path(r'<int:id>/<slug:slug>/picture/', views.person_picture, name='person_picture'),
    path(r'<int:id>/<slug:slug>/person_unverified_picture/', views.person_unverified_picture, name='person_unverified_picture'),
    path(r'<int:id>/ajax/employee/', ajax_views.person_employee, name='person_employee'),
    path(r'<int:id>/ajax/preferences/', ajax_views.person_preferences, name='person_preferences'),
    path(r'<int:id>/ajax/study/', ajax_views.person_study, name='person_study'),
    path(r'<int:id>/ajax/membership/payments/<int:membership>/', ajax_views.person_payments, name='person_pay'),
    path(r'<int:id>/ajax/membership/', ajax_views.person_membership, name='person_membership'),
    path(r'<int:id>/ajax/membership/new/', ajax_views.person_membership_new, name='person_membership_new'),
    path(r'<int:id>/ajax/membership/end/', ajax_views.person_membership_end, name='person_membership_end'),
    path(r'<int:id>/ajax/membership/<str:option>/', ajax_views.person_membership, name='person_membership'),
    path(r'<int:id>/ajax/mandate/', ajax_views.person_mandate, name='person_mandate'),
    path(r'<int:id>/ajax/mandate/new/', ajax_views.person_mandate_new, name='person_mandate_new'),
    path(r'<int:id>/ajax/mandate/activate/<int:mandate>/', ajax_views.person_mandate_activate, name='person_mandate_activate'),
    path(r'<int:id>/ajax/mandate/end/<int:mandate>/', ajax_views.person_mandate_end, name='person_mandate_end'),
    path(r'<int:id>/ajax/functions/', ajax_views.person_functions, name='person_functions'),

    path(r'ajax/autocomplete/name/', ajax_views.autocomplete_names, name='autocomplete'),
    path(r'ajax/autocomplete/cookie_corner/name/', ajax_views.autocomplete_names_cookie_corner, name='autocomplete_cookie_corner'),

    path(r'userinfo/', views.person_userinfo, name='person_userinfo'),
    path(r'groupinfo/', views.person_groupinfo, name='person_groupinfo'),
    path(r'send_link_code/<int:person_id>/', views.person_send_link_code, name='send_oauth_link_code'),

    path(r'payment/<int:pk>/delete/', PaymentDeleteView.as_view(), name='payment_delete'),

    path(r'birthdays/', views.birthdays, name='birthdays'),

    path(r'new/general/', views.RegisterNewGeneralWizardView.as_view(), name='person_new_general'),
    path(r'new/external/', views.RegisterNewExternalWizardView.as_view(), name='person_new_external'),
    path(r'new/employee/', views.RegisterNewEmployeeWizardView.as_view(), name='person_new_employee'),
    path(r'new/freshman/', views.RegisterNewFreshmanWizardView.as_view(), name='person_new_freshman'),
    path(r'preregister/freshman/', views.PreRegisterNewFreshmanWizardView.as_view(), name='person_preregister_freshman'),
    path(r'preregister/complete/', views.PreRegistrationCompleteView.as_view(), name='person_preregister_complete'),
    path(r'preregistration/', views.PreRegistrationStatus.as_view(), name='preregistration_status'),
    path(r'preregistration/print/', views.PreRegistrationPrintAll.as_view(), name='preregistration_print_all'),
    path(r'preregistration/print/dogroup/', views.PreRegistrationPrintDogroup.as_view(), name='preregistration_print_dogroup'),

    path(r'registration_form/<int:user>/<int:membership>/', views.registration_form, name='registration_form'),
    path(r'membership_form/<int:user>/<int:membership>/', views.membership_form, name='membership_form'),
    path(r'mandate_form/<int:mandate>/', views.mandate_form, name='mandate_form'),

    path(r'registration_check/', views.registration_check, name='registration_check'),
    path(r'registration_check/<int:id>/<slug:slug>/', views.registration_check_view, name='registration_check_view'),

    path(r'contact_list/', views.contact_list, name='contact_list'),
    path(r'export_csv/primary/', views.csv_student_number_primary, name='csv_studentnumber_primary'),
    path(r'export_csv/withoutbit/', views.csv_student_number_without_bit, name='csv_studentnumber_withoutbit'),

    path(r'dogroups/', views.DoGroupTreeView.as_view(), name='dogroups'),
    path(r'dogroups/data/', cache_page(60 * 60 * 24 * 30)(views.DoGroupTreeViewData.as_view()), name='dogroups_data'),

    path(r'books_list/', views.books_list, name='books_list'),


    # Old (dutch) URLs to not break permalinks
    path(r'statistieken/betalingen/', RedirectView.as_view(pattern_name='members:statistics_payments', permanent=True)),
    path(r'statistieken/', RedirectView.as_view(pattern_name='members:statistics', permanent=True)),
    path(r'<int:id>/<slug:slug>/pasfoto/', RedirectView.as_view(pattern_name='members:person_picture', permanent=True)),
    path(r'verjaardagen/', RedirectView.as_view(pattern_name='members:birthdays', permanent=True)),
    path(r'telefoonlijst/', RedirectView.as_view(pattern_name='members:contact_list', permanent=True)),
]
