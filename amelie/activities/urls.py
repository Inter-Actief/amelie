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
    path('', views.ActivityListView.as_view(), name='activities'),
    path('old/', views.OldActivityListView.as_view(), name='activities_old'),
    # URLs about the photo gallery
    path('photos/', views.photos, name='photos'),
    path('photos/<int:page>/', views.photos, name='photos'),
    path('photos/random/', views.random_photo, name='random_photo'),
    path('photos/upload/', views.photo_upload, name='photo_upload'),
    path('photos/upload/preview/<str:filename>', views.photo_upload_preview, name='photo_upload_preview'),
    path('photos/upload/files/', views.UploadPhotoFilesView.as_view(), name='photo_upload_files'),
    path('photos/upload/clear/', views.ClearPhotoUploadDirView.as_view(), name='photo_upload_clear'),

    # URLs about an activity
    path('<int:pk>/', views.ActivityDetailView.as_view(), name='activity'),
    path('<int:pk>/mailing/', views.activity_mailing, name='mailing'),
    path('<int:pk>/photos/random/', views.activity_random_photo, name='random_photo'),
    path('<int:pk>/photo/<int:photo>/', views.gallery_photo, name='gallery_photo'),
    path('<int:pk>/photo/<int:photo>/togglevisibility', views.toggle_visibility, name='gallery_photo_toggle_visibility'),
    path('<int:pk>/photo/<int:photo>/delete', views.delete_photo, name='gellery_photo_delete'),
    path('<int:pk>/photos/', views.gallery, name='gallery'),
    path('<int:pk>/photos/<int:page>/', views.gallery, name='gallery'),

    path('<int:pk>/edit/', ActivityUpdateView.as_view(), name='edit'),
    path('new/', ActivityCreateView.as_view(), name='new'),
    path('<int:pk>/cancel/', views.ActivityCancelView.as_view(), name='cancel'),
    path('<int:pk>/delete/', views.ActivityDeleteView.as_view(), name='delete'),

    # URLs about enrollments
    path('<int:pk>/enrollment/', views.ActivityEnrollView.as_view(), name='enrollment'),
    path('<int:pk>/enrollment/<int:person_id>/', views.ActivityEnrollView.as_view(), name='enrollment_person'),
    path('<int:pk>/enrollment/search/', views.ActivityEnrollSearchPersonView.as_view(), name='enrollment_person_search'),
    path('<int:pk>/enrollment/unenroll/', views.ActivityUnenrollView.as_view(), name='unenrollment'),
    path('<int:pk>/enrollment/<int:person_id>/unenroll/', views.ActivityUnenrollView.as_view(), name='unenrollment_person'),
    path('<int:pk>/enrollment/edit/', views.ActivityEditEnrollView.as_view(), name='editenrollment'),
    path('<int:pk>/enrollment/<int:person_id>/edit/', views.ActivityEditEnrollView.as_view(), name='editenrollment_person'),
    path('<int:pk>/enrollment/export/', views.DataExport.as_view(), name='enrollment_data_export'),

    # URLs about adding a new enrollmentoption to an activity
    path('<int:pk>/enrollmentoptions/checkbox/new/', EnrollmentoptionCreateView.as_view(model=EnrollmentoptionCheckbox), name='enrollmentoption_checkbox_new'),
    path('<int:pk>/enrollmentoptions/numeric/new/', EnrollmentoptionCreateView.as_view(model=EnrollmentoptionNumeric), name='enrollmentoption_numeric_new'),
    path('<int:pk>/enrollmentoptions/question/new/', EnrollmentoptionCreateView.as_view(model=EnrollmentoptionQuestion), name='enrollmentoption_question_new'),
    path('<int:pk>/enrollmentoptions/food/new/', EnrollmentoptionCreateView.as_view(model=EnrollmentoptionFood), name='enrollmentoption_food_new'),
    path('<int:pk>/enrollmentoptions/', EnrollmentoptionListView.as_view(), name='enrollmentoption_list'),

    # URLs about editing enrollmentoptions
    path('enrollmentoptions/<int:pk>/edit/', EnrollmentoptionUpdateView.as_view(), name='enrollmentoption_edit'),
    path('enrollmentoptions/<int:pk>/delete/', EnrollmentoptionDeleteView.as_view(), name='enrollmentoption_delete'),

    # URLs about calendars
    path('calendar.ics', views.ActivitiesICSView.as_view(), name='activities_ics'),
    re_path(r'calendar_(?P<lang>(nl|en))\.ics', views.ActivitiesICSView.as_view(), name='activities_ics_international'),
    path('<int:pk>/activity.ics', views.ActivityICSView.as_view(), name='ics'),

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

    # Activity label filtering (last because it would override other URLs otherwise)
    path('<str:act_type>', views.ActivityListView.as_view(), name='activities_type'),
]
