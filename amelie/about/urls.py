from django.urls import path

from amelie.about import views
from amelie.about.views import PageRedirectView


app_name = 'about'

urlpatterns = [
    # For compatibility, to redirect old page urls
    path('nl/<slug:slug>/', PageRedirectView.as_view(), name='page_redirect'),

    path('', views.pages, name='pages'),
    path('new/', views.page_new, name='page_new'),
    path('<int:pk>/<slug:slug>/', views.page, name='page'),
    path('<int:pk>/<slug:slug>/edit/', views.page_edit, name='page_edit'),
    path('<int:pk>/<slug:slug>/delete/', views.page_delete, name='page_delete'),
]
