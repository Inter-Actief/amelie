from django.urls import path

from amelie.narrowcasting import views


app_name = 'narrowcasting'

urlpatterns = [
    path('', views.index, name='index'),
    path('room/', views.room, name='room'),
    path('room/pc_status/', views.room_pcstatus, name='room_pcstatus'),
    path('room/link_spotify/', views.room_spotify_callback,
         name='room_spotify_callback'),
    path('room/spotify/', views.room_spotify_now_playing,
         name='room_spotify_now_playing'),
    path('room/pause_spotify/', views.room_spotify_pause,
         name='room_spotify_now_playing'),
    path('room/play_spotify/', views.room_spotify_play,
         name='room_spotify_now_playing'),
    path('promotions/', views.promo_list, name='promo_list'),
    path('promotions/<int:page>', views.promo_list, name='promo_list'),
    path('promotions/create/', views.promo_create, name='promo_create'),
    path('promotions/<int:id>/update/', views.promo_update, name='promo_update'),
    path('promotions/<int:id>/delete/', views.promo_delete, name='promo_delete'),
]
