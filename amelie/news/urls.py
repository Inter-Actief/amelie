from django.urls import path

from amelie.news import views


app_name = 'news'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('new/', views.news_item_new, name='new'),
    path('<int:id>/<int:year>/<int:month>/<int:day>/<slug:slug>/', views.news_item, name='news-item'),
    path('<int:id>/<int:year>/<int:month>/<int:day>/<slug:slug>/edit/', views.news_item_edit, name='edit'),
    path('<int:id>/<int:year>/<int:month>/<int:day>/<slug:slug>/delete/', views.news_item_delete, name='delete'),
]
