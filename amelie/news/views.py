from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.template.defaultfilters import slugify
from django.utils.translation import gettext as _

from amelie.news.forms import NewsItemForm, NewsItemBoardForm
from amelie.news.models import NewsItem
from amelie.members.models import Committee
from amelie.tools import amelie_messages
from amelie.tools.decorators import require_actief, require_board
from amelie.tools.paginator import RangedPaginator


@require_actief
def news_item_edit(request, id, year, month, day, slug):
    obj = get_object_or_404(NewsItem, id=id)
    if not obj.can_edit(request.person):
        return redirect(obj)

    is_new = False

    form_type = NewsItemBoardForm if request.is_board else NewsItemForm
    form = form_type(request.POST, instance=obj) if request.method == "POST" else form_type(instance=obj)

    if not request.is_board:
        form.fields['publisher'].queryset = request.person.current_committees()

    if request.method == "POST" and form.is_valid():
        news_item = form.save()

        if not (news_item.title_en and news_item.introduction_en and news_item.content_en):
            amelie_messages.with_actions(request, messages.WARNING,
                                         _('You did not fill in an English title/introduction/description.'),
                                         [(_('edit news message'),
                                           reverse('news:edit',
                                                   args=[news_item.id, news_item.publication_date.year,
                                                         news_item.publication_date.month,
                                                         news_item.publication_date.day,
                                                         slugify(news_item.slug)]))])

        return HttpResponseRedirect(news_item.get_absolute_url())

    return render(request, 'news_item_form.html', locals())


@require_board
def news_item_delete(request, id, year, month, day, slug):
    obj = get_object_or_404(NewsItem, id=id)
    if request.method == "POST":
        obj.delete()
        return HttpResponseRedirect("/")
    return render(request, 'news_item_delete.html', locals())


@require_actief
def news_item_new(request):
    form_type = NewsItemBoardForm if request.is_board else NewsItemForm
    form = form_type() if request.method != "POST" else form_type(request.POST)

    if "education" in request.GET:
        form.fields['publisher'].initial = Committee.education_committee()

    is_new = True

    if not request.is_board:
        form.fields['publisher'].queryset = request.person.current_committees()

    if request.method == "POST" and form.is_valid():
        news_item = form.save(commit=False)
        news_item.author = request.person
        news_item.save()

        if not (news_item.title_en and news_item.introduction_en and news_item.content_en):
            amelie_messages.with_actions(request, messages.WARNING,
                                         _('You did not fill in an English title/introduction/description.'),
                                         [(_('edit news message'),
                                           reverse('news:edit',
                                                   args=[news_item.id, news_item.publication_date.year,
                                                         news_item.publication_date.month,
                                                         news_item.publication_date.day,
                                                         slugify(news_item.slug)]))])

        return HttpResponseRedirect(news_item.get_absolute_url())

    return render(request, 'news_item_form.html', locals())


def overview(request):
    """ Gives an overview of all news items """
    news_list = NewsItem.objects.all()

    pages = RangedPaginator(news_list, 12)
    page = request.GET.get('page')

    try:
        news = pages.page(page)
    except PageNotAnInteger:
        news = pages.page(1)
    except EmptyPage:
        news = pages.page(pages.num_pages)

    pages.set_page_range(news, 7)

    return render(request, 'news_items.html', locals())


def news_item(request, id, year, month, day, slug):
    """ Gives the page for the indicated news item """
    obj = get_object_or_404(NewsItem, id=id)
    if hasattr(request, 'person'):
        is_board = hasattr(request, 'person') and request.is_board
        can_edit = obj.can_edit(request.person)
        can_delete = obj.can_delete(request.person)
    return render(request, 'news_item.html', locals())
