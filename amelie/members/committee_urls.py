from django.urls import path

from amelie.members import ajax_views, committee_views


urlpatterns = [
    path('', committee_views.committees, name='committees'),
    path('new/', committee_views.committee_new, name='committee_new'),
    path('<int:id>/<slug:slug>/', committee_views.committee, name='committee'),
    path('<int:id>/<slug:slug>/edit/', committee_views.committee_edit, name='committee_edit'),
    path('<int:id>/<slug:slug>/members/', committee_views.committee_members_edit,
        name='committee_members_edit'),
    path('<int:id>/<slug:slug>/member/<int:function_id>', committee_views.committee_single_member_edit, name='committee_single_member_edit'),

    path('<int:id>/<slug:slug>/pictures/random/', committee_views.committee_random_picture,
        name='committee_random_picture'),
    path('<int:id>/<slug:slug>/agenda.ics', committee_views.committee_agenda_ics,
        name='committee_agenda_ics'),

    path('<int:id>/<slug:slug>/ajax/data/', ajax_views.committee_data, name='committee_data'),

    # Old (dutch) URLs to not break permalinks
    path('<int:id>/<slug:slug>/fotos/willekeurig/', committee_views.committee_random_picture),
    path('<int:id>/<slug:slug>/ajax/gegevens/', ajax_views.committee_data),
]
