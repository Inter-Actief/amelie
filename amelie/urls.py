import oauth2_provider.views

from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.urls import reverse_lazy, path, re_path
from django.contrib.auth.views import LogoutView
from django.views.generic.base import RedirectView
from django.views.static import serve

from amelie import views
from amelie.activities.feeds import Activities
from amelie.news.feeds import LatestNews
from amelie.oauth.views import RequestOAuth

urlpatterns = [

    # Site workings
    path('admin/doc/', include('django.contrib.admindocs.urls')),
    path('admin/', admin.site.urls),
    path('legacy_login/', views.login, name='legacy_login'),
    path('legacy_logout/', LogoutView.as_view(), name='legacy_logout'),
    path('i18n/', include('django.conf.urls.i18n')),
    path('profile/', views.profile_overview, name='profile_overview'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('oidc/', include('mozilla_django_oidc.urls')),

    # General views
    path('', views.frontpage, name='frontpage'),

    # Redirect to privacy.ia.utwente.nl (for old links)
    path('privacy/', RedirectView.as_view(url='https://privacy.ia.utwente.nl/', permanent=True)),

    # Apps
    path('about/', include('amelie.about.urls')),
    path('education/', include('amelie.education.urls')),
    path('', include('amelie.members.urls')),
    path('activities/', include('amelie.activities.urls')),
    path('news/', include('amelie.news.urls')),
    path('companies/', include('amelie.companies.urls')),
    path('narrowcasting/', include('amelie.narrowcasting.urls')),
    path('personal_tab/', include('amelie.personal_tab.urls')),
    path('twitter/', include('amelie.twitter.urls')),
    path('claudia/', include('amelie.claudia.claudia_urls')),
    path('account/', include('amelie.claudia.account_urls')),
    path('weekmail/', include('amelie.weekmail.urls')),
    path('tools/', include('amelie.tools.urls')),
    path('room_duty/', include('amelie.room_duty.urls')),
    path('gmm/', include('amelie.gmm.urls')),
    path('ckeditor_uploader/', include('ckeditor_uploader.urls')),
    path('statistics/', include('amelie.statistics.urls')),
    path('blame/', include('amelie.blame.urls')),
    path('videos/', include('amelie.videos.urls')),
    path('data_export/', include('amelie.data_export.urls')),
    path('publications/', include('amelie.publications.urls')),
    path('participation/', include('amelie.calendar.participation_urls')),

    # API
    path('api/', include('amelie.api.urls')),

    # Feeds
    path('feeds/', include(
        ([
            path('nieuws/', RedirectView.as_view(pattern_name="feeds:latest-news", permanent=True)),
            path('news/', LatestNews(), name="latest-news"),
            path('activiteiten/', RedirectView.as_view(pattern_name="feeds:activities", permanent=True)),
            path('activities/', Activities(), name="activities"),
        ], 'feeds'),
        namespace='feeds')
    ),

    # OAuth2 provider for legacy API
    path('o/authorize/', oauth2_provider.views.AuthorizationView.as_view(),
        name="authorize"),
    path('o/token/', oauth2_provider.views.TokenView.as_view(),
        name="token"),
    path('o/revoke_token/<int:pk>/',
        views.AuthorizedTokenDeleteViewAmelieWrapper.as_view(success_url=reverse_lazy('profile_overview')),
        name="revoke-token"),
    # Include oauth request_access url here because the oauth app urls are not included due to old urls.
    path('oauth/request_access/', RequestOAuth.as_view(), name="request_oauth"),

    # SAML2 IdP
    path('saml2idp/', include('djangosaml2idp.urls')),

    # Other
    path('favicon.ico',
        RedirectView.as_view(
            url='%sfavicon.ico' % settings.STATIC_URL,
            permanent=False),
        name='favicon_redirect'),
    path('robots.txt',
        RedirectView.as_view(
            url='%srobots.txt' % settings.STATIC_URL,
            permanent=False),
        name='robots_redirect'),
    path('.well-known/security.txt', views.security_txt, name='security_txt'),

    # Redirects for old dutch URL's for permalinks and such
    path('over/<str:path>', RedirectView.as_view(url='/about/%(path)s', permanent=True)),
    path('nieuws/<str:path>', RedirectView.as_view(url='/news/%(path)s', permanent=True)),
    path('onderwijs/<str:path>', RedirectView.as_view(url='/education/%(path)s', permanent=True)),
    path('activiteiten/<str:path>', RedirectView.as_view(url='/activities/%(path)s', permanent=True)),
    path('nieuws/<str:path>', RedirectView.as_view(url='/news/%(path)s', permanent=True)),
    path('bedrijven/<str:path>', RedirectView.as_view(url='/companies/%(path)s', permanent=True)),
    path('statistieken/<str:path>', RedirectView.as_view(url='/statistics/%(path)s', permanent=True)),
    path('kamerdienst/<str:path>', RedirectView.as_view(url='/room_duty/%(path)s', permanent=True)),
    path('streeplijst/<str:path>', RedirectView.as_view(url='/personal_tab/%(path)s', permanent=True)),
]
admin.autodiscover()

if settings.ENABLE_REQUEST_PROFILING:
    # Django-silk profiling views
    urlpatterns += [
        path('silk/', include('silk.urls', namespace='silk')),
    ]

if settings.DEBUG:
    # Static and media files in development mode
    urlpatterns += [
        re_path(r'^%s(?P<path>.*)$' % (settings.MEDIA_URL[1:]), serve, {'document_root': settings.MEDIA_ROOT},
            name='media'),
        re_path(r'^%s(?P<path>.*)$' % (settings.STATIC_URL[1:]), serve, {'document_root': settings.STATIC_ROOT},
            name='static'),
    ]

    # Translation application for development
    urlpatterns += [
        path('translations/', include('rosetta.urls'), name='translations')
    ]


if settings.DEBUG_TOOLBAR:
    import debug_toolbar
    # Django debug toolbar
    urlpatterns += [
        path('__debugtoolbar__/', include(debug_toolbar.urls), name='django_debug_toolbar')
    ]

# Redirect for 500 errors
handler500 = views.server_error
