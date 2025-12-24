from django.urls import path, re_path
from django.urls import reverse_lazy
from django.views.generic import RedirectView

from amelie.personal_tab import pos_views, views, register, print_views
from amelie.personal_tab.views import ActivityTransactionDetail, \
    AlexiaTransactionDetail, CookieCornerTransactionDetail, \
    ReversalTransactionDetail, TransactionDetail, AuthorizationTerminateView, \
    AuthorizationAnonymizeView, CustomTransactionUpdate, CustomTransactionDelete, CookieCornerTransactionUpdate, \
    CookieCornerTransactionDelete

app_name = 'personal_tab'

urlpatterns = [
    path('', views.overview, name='overview'),

    path('price_list/', views.price_list, name='price_list'),

    # Short URL to a person's own dashboard
    path('me/', views.my_dashboard, name='my_dashboard'),

    path('transactions/', views.transaction_overview, name='transactions'),
    path('transactions/<int:date_from>/<int:date_to>/', views.transaction_overview, name='transactions'),
    path('transactions/activity/<int:pk>/', ActivityTransactionDetail.as_view(), name='activity_transaction_detail'),
    path('transactions/alexia/<int:pk>/', AlexiaTransactionDetail.as_view(), name='alexia_transaction_detail'),
    path('transactions/cookie_corner/<int:pk>/', CookieCornerTransactionDetail.as_view(),
        name='cookie_corner_transaction_detail'),
    path('transactions/cookie_corner/<int:pk>/edit/', CookieCornerTransactionUpdate.as_view(),
        name='cookie_corner_transaction_update'),
    path('transactions/cookie_corner/<int:pk>/delete/', CookieCornerTransactionDelete.as_view(),
        name='cookie_corner_transaction_delete'),

    path('wrapped', views.cookie_corner_wrapped_main, name='cookie_corner_wrapped'),
    path('wrapped/<int:year>/', views.cookie_corner_wrapped_main, name='cookie_corner_wrapped_year'),

    path('transactions/reversal/<int:pk>/', ReversalTransactionDetail.as_view(), name='reversal_transaction_detail'),
    path('transactions/<int:pk>/', TransactionDetail.as_view(), name='transaction_detail'),
    path('transactions/<int:pk>/edit/', CustomTransactionUpdate.as_view(), name='transaction_update'),
    path('transactions/<int:pk>/delete/', CustomTransactionDelete.as_view(), name='transaction_delete'),

    path('exam_cookie_credit/', views.exam_cookie_credit, name='exam_cookie_credit'),
    path('exam_cookie_credit/<int:date_from>/<int:date_to>/', views.exam_cookie_credit,
        name='exam_cookie_credit'),

    path('person/<int:pk>/<slug:slug>/', views.dashboard, name='dashboard'),
    path('person/<int:pk>/<slug:slug>/transactions/', views.person_transactions, name='person_transactions'),
    path('person/<int:pk>/<slug:slug>/transactions/<int:date_from>/<int:date_to>/',
        views.person_transactions, name='person_transactions'),

    path('person/<int:person_id>/<slug:slug>/new/<str:transaction_type>/', views.person_new_transaction,
        name='person_new_transaction'),
    path('person/<int:person_id>/<slug:slug>/debt_collection_instructions/',
        views.person_debt_collection_instructions, name='person_debt_collection_instructions'),

    path('person/<int:person_id>/<slug:slug>/exam_cookie_credit/', views.person_exam_cookie_credit,
        name='person_exam_cookie_credit'),
    path('person/<int:person_id>/<slug:slug>/exam_cookie_credit/<int:date_from>/<int:date_to>/',
        views.person_exam_cookie_credit, name='person_exam_cookie_credit'),
    path('person/<int:person_id>/<slug:slug>/exam_cookie_credit/new/', views.person_exam_cookie_credit_new,
        name='person_exam_cookie_credit_new'),

    path('rfid/<int:rfid_id>/edit/<str:status>/', views.rfid_change_status, name='rfid_change_status'),
    path('rfid/<int:rfid_id>/remove/', views.rfid_remove, name='rfid_remove'),

    path('export/', views.export, name='export'),
    path('export/<int:date_from>/<int:date_to>/', views.export, name='export'),
    path('export/<int:date_from>/<int:date_to>/csv/', views.export_csv, name='export_csv'),

    path('statistics/', views.statistics_form, name='statistics_form'),
    path('statistics/<int:date_from>/<int:date_to>/<str:checkboxes>/', views.statistics, name='statistics'),

    path('balance/', views.balance, name='balance'),
    path('balance/<int:dt_str>/', views.balance, name='balance'),

    path('activity/<int:event_id>/', views.activity_transactions, name='event'),

    path('debt_collection/', views.debt_collection_list, name='debt_collection_list'),
    path('debt_collection/new/', views.debt_collection_new, name='debt_collection_new'),
    path('debt_collection/<int:id>/', views.debt_collection_view, name='debt_collection_view'),
    path('debt_collection/<int:assignment_id>/export/', views.debt_collection_export, name='debt_collection_export'),
    path('debt_collection/<int:assignment_id>/mailing/', views.debt_collection_mailing, name='debt_collection_mailing'),
    path('debt_collection/<int:assignment_id>/mailing/contribution/', views.debt_collection_mailing_contribution,
        name='debt_collection_mailing_contribution'),
    path('debt_collection/<int:assignment_id>/mailing/cookie_corner/', views.debt_collection_mailing_cookie_corner,
        name='debt_collection_mailing_cookie_corner'),

    path('debt_collection_instruction/<int:id>/', views.debt_collection_instruction_view,
        name='debt_collection_instruction_view'),
    path('debt_collection_instruction/<int:id>/reversal/', views.debt_collection_instruction_reversal,
        name='debt_collection_instruction_reversal'),

    path('batch/<int:id>/', views.process_batch, name='process_batch'),

    path('authorization/', views.authorization_list, name='authorization_list'),
    path('authorization/<int:authorization_id>/', views.authorization_view, name='authorization_view'),
    path('authorization/<int:authorization_id>/amendement/', views.authorization_amendment,
        name='authorization_amendment'),
    path('authorization/terminate/', AuthorizationTerminateView.as_view(), name='authorization_terminate'),
    path('authorization/anonymize/', AuthorizationAnonymizeView.as_view(), name='authorization_anonymize'),

    # Point of sale views
    path('pos/', pos_views.PosHomeView.as_view(), name='pos_index'),
    path('pos/process_rfid/', pos_views.PosProcessRFIDView.as_view(), name='pos_process'),
    re_path(r'^pos/qr/(?P<type>(login|register))/$', pos_views.PosGenerateQRView.as_view(), name='pos_generate_qr'),
    path('pos/verify/<uuid:uuid>/', pos_views.PosVerifyTokenView.as_view(), name='pos_verify'),
    path('pos/login_check/<uuid:uuid>/', pos_views.PosCheckLoginAjaxView.as_view(), name='pos_check'),
    path('pos/user_logout/', pos_views.PosLogoutView.as_view(), name='pos_logout'),
    path('pos/shop/', pos_views.PosShopView.as_view(), name='pos_shop'),
    path('pos/register_external/', pos_views.PosRegisterExternalCardView.as_view(), name='pos_register_external'),
    path('pos/scan_external/', pos_views.PosScanExternalCardView.as_view(), name='pos_scan_external'),

    # RFID card registration views
    path('register/', register.CardRegistrationIndex.as_view(), name='register_index'),
    path('register/scan/', register.CardRegistrationScan.as_view(), name='register_scan'),

    # Document printing views
    path('print/', print_views.PrintIndexView.as_view(), name='print_index'),
    path('print/refund/<int:pk>/', print_views.PrintRefundConfirmView.as_view(), name='print_refund'),
    path('print/log/', print_views.PrintLogView.as_view(), name='print_log'),
    path('print/status/<str:printer_key>/', print_views.printer_status, name='printer_status'),

    # Redirects for old Dutch URL's that people might have bookmarked
    path('mijn/', RedirectView.as_view(url=reverse_lazy("personal_tab:my_dashboard"), permanent=True)),

]
