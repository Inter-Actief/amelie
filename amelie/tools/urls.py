from django.urls import path, re_path

from amelie.tools import views
from amelie.tools.views import MailPreview


app_name = 'tools'

urlpatterns = [
    path('logging_config/', views.logging_config, name='logging_info'),
    path('data_export_statistics/', views.DataExportStatistics.as_view(), name='data_export_statistics'),
    path('flash/', views.flash, name='flash'),
    path('mail/', MailPreview.as_view(), name='mail_preview'),
    re_path(r'^mail/(?P<lang>(nl|en))/(?P<template_name>.*)/$', MailPreview.as_view(), name='mail_preview'),
    path('mailtest/', views.mail_template_test, name='mail_template_test'),
]
