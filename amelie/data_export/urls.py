from django.urls import path

from amelie.data_export import views


app_name = 'data_export'

urlpatterns = [
    path('', views.RequestDataExportView.as_view(), name='request_export'),
    path('<slug:slug>/', views.DataExportDetailView.as_view(), name='export_details'),
    path('<slug:slug>/dl/', views.DataExportDownloadView.as_view(), name='download_export'),
    path('<slug:slug>/ajax/', views.DataExportAjaxView.as_view(), name='export_ajax'),
]
