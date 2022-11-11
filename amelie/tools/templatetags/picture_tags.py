from django import template
from django.urls import reverse

register = template.Library()


@register.simple_tag
def picture_activities_url(page):
    return reverse('activities:photos', kwargs={'page': page, })


@register.simple_tag
def picture_url(activity, picture):
    return reverse('activities:gallery_photo', kwargs={'pk': activity.id, 'photo': picture.pk, })


@register.simple_tag
def picture_gallery_url(activity, page):
    return reverse('activities:gallery', kwargs={'pk': activity.id, 'page': page, })
