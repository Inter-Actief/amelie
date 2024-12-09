from django.urls import path

from amelie.narrowcasting import views


app_name = 'narrowcasting'

urlpatterns = [
    path('', views.index, name='index'),
    path('room/', views.room, name='room'),
    path('room/link_spotify/', views.room_spotify_callback, name='room_spotify_callback'),
    path('room/spotify/', views.room_spotify_now_playing, name='room_spotify_now_playing'),
    path('room/pause_spotify/', views.room_spotify_pause, name='room_spotify_now_playing'),
    path('room/play_spotify/', views.room_spotify_play, name='room_spotify_now_playing'),
]
