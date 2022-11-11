from django.urls import path

from amelie.videos import views


app_name = 'videos'

urlpatterns = [
    path('', views.VideoList.as_view(), name='list_videos'),

    path('new/yt/', views.YoutubeVideoCreate.as_view(), name='new_yt_video'),
    path('new/ia/', views.StreamingVideoCreate.as_view(), name='new_ia_video'),
    path('new/yt/<str:video_id>/', views.YoutubeVideoCreate.as_view(), name='new_predefined_yt_video'),
    path('new/ia/<str:video_id>/', views.StreamingVideoCreate.as_view(), name='new_predefined_ia_video'),

    path('yt/<str:pk>/', views.YoutubeVideoDetail.as_view(), name='single_yt_video'),
    path('ia/<str:pk>/', views.StreamingVideoDetail.as_view(), name='single_ia_video'),
    path('yt/<str:pk>/edit/', views.YoutubeVideoUpdate.as_view(), name='edit_yt_video'),
    path('ia/<str:pk>/edit/', views.StreamingVideoUpdate.as_view(), name='edit_ia_video'),
    path('<str:pk>/delete/', views.VideoDelete.as_view(), name='delete_video'),
]
