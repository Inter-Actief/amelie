from django.urls import path, re_path

from amelie.weekmail import views
from amelie.weekmail.views import WeekMailWizard, WeekMailCreateView, WeekMailUpdateView, WeekMailListView, \
    WeekMailPreview, WeekMailNewsArticleDeleteView, WeekMailNewsArticleUpdateView, \
    WeekMailNewsArticleCreateView, NewsArticleUpdateView, ActivityUpdateView


app_name = 'weekmail'

urlpatterns = [
    path('', WeekMailListView.as_view(), name='list_view'),
    # There are two weekmail_preview matches
    # django could not figure out that "nl" or "en" was optional
    path('archive/<int:pk>/', WeekMailPreview.as_view(), name='preview'),
    re_path(r'^archive/(?P<pk>\d+)/(?P<lang>(nl|en))/$', WeekMailPreview.as_view(), name='preview'),
    path('<int:pk>/wizard/', WeekMailWizard.as_view(), name='wizard'),
    path('<int:pk>/update/', WeekMailUpdateView.as_view(), name='update'),
    path('<int:pk>/update/add/extra_news_article/', WeekMailNewsArticleCreateView.as_view(),
         name='extra_news_article_add'),
    path('<int:pk1>/detail/extra_news_article/<int:pk>/delete/', WeekMailNewsArticleDeleteView.as_view(),
         name='extra_news_article_delete'),
    path('<int:pk1>/detail/extra_news_article/<int:pk>/update/', WeekMailNewsArticleUpdateView.as_view(),
         name='extra_news_article_update'),
    path('<int:pk1>/detail/news_article/<int:pk>/update/', NewsArticleUpdateView.as_view(), name='news_article_update'),
    path('<int:pk1>/detail/activity/<int:pk>/update/', ActivityUpdateView.as_view(), name='activity_update'),
    path('new/', WeekMailCreateView.as_view(), name='new'),
    path('send/<int:pk>/', views.send_weekmail, name='send_weekmail'),


    # Old Dutch URLs so permalinks don't break
    path('archief/<int:pk>/', WeekMailPreview.as_view(), name='voorbeeld'),
    re_path(r'^archief/(?P<pk>\d+)/(?P<lang>(nl|en))/$', WeekMailPreview.as_view(), name='voorbeeld'),
]
