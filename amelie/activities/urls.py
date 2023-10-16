from django.urls import path, re_path
from django.views.generic.base import RedirectView

from amelie.activities.models import EnrollmentoptionCheckbox, EnrollmentoptionFood, EnrollmentoptionQuestion, \
    EnrollmentoptionNumeric
from amelie.activities import views
from amelie.activities.views import EnrollmentoptionCreateView, ActivityUpdateView, ActivityCreateView, \
    EnrollmentoptionUpdateView, EnrollmentoptionDeleteView, EnrollmentoptionListView

"""
There are two conventions used in this file, one is deprecated and thus redirected:
    pk/year/month/day/slug/
And one that we want to see/like:
    pk/action/subaction/subsubaction/       if there is an activity id
    action/subaction/subsubaction/          if there is no activity id
    action/pk/subaction/                    if it is about an object that is not directly an Activity
In practice these are urls like:
    new/
    12/photos/
    enrollmentoptions/12/edit

Names have been prefixed with 'activity-', this can be changed in amelie/urls.py
"""

app_name = 'activities'

urlpatterns = [
    # URLs that are not about a specific activity
    path('', views.activities, name='activities'),
    path('old/', views.activities_old, name='activities_old'),
    # URLs about the photo gallery
    path('photos/', views.photos, name='photos'),
    path('photos/<int:page>/', views.photos, name='photos'),
    path('photos/random/', views.random_photo, name='random_photo'),
    path('photos/upload/', views.photo_upload, name='photo_upload'),
    path('photos/upload/preview/<str:filename>', views.photo_upload_preview, name='photo_upload_preview'),
    path('photos/upload/files/', views.UploadPhotoFilesView.as_view(), name='photo_upload_files'),
    path('photos/upload/clear/', views.ClearPhotoUploadDirView.as_view(), name='photo_upload_clear'),

    # URLs about an activity
    path('<int:pk>/', views.activity, name='activity'),
    path('<int:pk>/mailing/', views.activity_mailing, name='mailing'),
    path('<int:pk>/photos/random/', views.activity_random_photo, name='random_photo'),
    path('<int:pk>/photo/<int:photo>/', views.gallery_photo, name='gallery_photo'),
    path('<int:pk>/photos/', views.gallery, name='gallery'),
    path('<int:pk>/photos/<int:page>/', views.gallery, name='gallery'),

    path('<int:pk>/edit/', ActivityUpdateView.as_view(), name='edit'),
    path('new/', ActivityCreateView.as_view(), name='new'),
    path('<int:pk>/cancel/', views.activity_cancel, name='cancel'),
    path('<int:pk>/delete/', views.activity_delete, name='delete'),

    # URLs about enrollments
    path('<int:pk>/enrollment/', views.activity_enrollment, name='enrollment'),
    path('<int:pk>/enrollment_export/', views.DataExport.as_view(), name='enrollment_data_export'),
    path('<int:pk>/enrollmentform/', views.activity_enrollment_self, name='enrollment_self'),
    path('<int:pk>/enrollmentform/search/', views.activity_enrollment_person_search, name='enrollment_person_search'),
    path('<int:pk>/enrollmentform/<int:person_id>/', views.activity_enrollment_person, name='enrollment_person'),
    path('<int:pk>/unenrollment/<int:person_id>/', views.activity_unenrollment, name='unenrollment'),
    path('<int:pk>/unenrollment/', views.activity_unenrollment_self, name='unenrollment_self'),
    path('<int:pk>/edit_enrollment/', views.activity_editenrollment_self, name='editenrollment_self'),
    path('<int:pk>/edit_enrollment/<int:person_id>/', views.activity_editenrollment_other, name='editenrollment_other'),

    # URLs about adding a new enrollmentoption to an activity
    path('<int:pk>/enrollmentoptions/checkbox/new/', EnrollmentoptionCreateView.as_view(model=EnrollmentoptionCheckbox), name='enrollmentoption_checkbox_new'),
    path('<int:pk>/enrollmentoptions/numeric/new/', EnrollmentoptionCreateView.as_view(model=EnrollmentoptionNumeric), name='enrollmentoption_numeric_new'),
    path('<int:pk>/enrollmentoptions/question/new/', EnrollmentoptionCreateView.as_view(model=EnrollmentoptionQuestion), name='enrollmentoption_question_new'),
    path('<int:pk>/enrollmentoptions/food/new/', EnrollmentoptionCreateView.as_view(model=EnrollmentoptionFood), name='enrollmentoption_food_new'),
    path('<int:pk>/enrollmentoptions/', EnrollmentoptionListView.as_view(), name='enrollmentoption_list'),

    # URLs about editing enrollmentoptions
    path('enrollmentoptions/<int:pk>/edit/', EnrollmentoptionUpdateView.as_view(), name='enrollmentoption_edit'),
    path('enrollmentoptions/<int:pk>/delete/', EnrollmentoptionDeleteView.as_view(), name='enrollmentoption_delete'),

    # URLs about calendars, two times due to reverse-urls
    path('calendar.ics', views.activities_ics, name='activities_ics'),
    re_path(r'calendar_(?P<lang>(nl|en))\.ics', views.activities_ics, name='activities_ics_international'),
    path('<int:pk>/activity.ics', views.activity_ics, name='ics'),

    # URLs for the eventdesk check pages
    path('eventdesk/', views.EventDeskMessageList.as_view(), name='eventdesk_list'),
    path('eventdesk/<int:pk>/history/', views.EventDeskHistory.as_view(), name='eventdesk_history'),
    path('eventdesk/<int:pk>/detail/', views.EventDeskMessageDetail.as_view(), name='eventdesk_detail'),
    path('eventdesk/<int:pk>/match/', views.EventDeskMatch.as_view(), name='eventdesk_match'),
    path('eventdesk/<int:pk>/unmatch/', views.EventDeskRemoveMatch.as_view(), name='eventdesk_unmatch'),

    # Redirect URLs for old dutch URLs
    path('kalender.ics', RedirectView.as_view(url='/activities/calendar_nl.ics', permanent=True)),
    re_path(r'kalender_(?P<lang>(nl|en))\.ics', RedirectView.as_view(url='/activities/calendar_%(lang)s.ics',
                                                                     permanent=True)),
    path('<int:pk>/activiteit.ics', RedirectView.as_view(url='/activities/%(pk)s/activity.ics', permanent=True)),
]
