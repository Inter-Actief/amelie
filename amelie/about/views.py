from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.views.generic.base import RedirectView

from amelie.about.forms import PageForm
from amelie.about.models import Page
from amelie.tools.decorators import require_committee


class PageRedirectView(RedirectView):
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        page_obj = get_object_or_404(Page, slug_nl=kwargs["slug"])

        return page_obj.get_absolute_url()


def page(request, pk, slug):
    obj = get_object_or_404(Page, pk=pk)
    is_www = (hasattr(request, 'is_board') and request.is_board) or \
             (hasattr(request, 'person') and request.person.function_set.filter(committee__abbreviation='WWW',
                                                                                end__isnull=True))
    is_educational = hasattr(request, 'person') and request.person.function_set.filter(committee__abbreviation='OnderwijsCommissie',
                                                                                end__isnull=True)
    return render(request, 'page.html', {'obj': obj, 'is_www': is_www, 'is_educational': is_educational})


def page_edit(request, pk, slug):
    obj = get_object_or_404(Page, pk=pk)
    if hasattr(request, 'person') and (
        request.person.is_board() or request.person.function_set.filter(committee__abbreviation='WWW',
                                                                        end__isnull=True).exists() or (
            obj.educational and request.person.function_set.filter(committee__abbreviation='OnderwijsCommissie',
                                                                   end__isnull=True).exists())):
        form = PageForm(instance=obj) if request.method != "POST" else PageForm(request.POST, instance=obj)
        is_new = False

        if request.method == "POST" and form.is_valid():
            page_obj = form.save()
            return HttpResponseRedirect(page_obj.get_absolute_url())

        return render(request, 'page_form.html', {
            'obj': obj,
            'form': form,
            'is_new': is_new
        })
    return render(request, '403.html')


def page_delete(request, pk, slug):
    obj = get_object_or_404(Page, pk=pk)
    if hasattr(request, 'person') and (
        request.person.is_board() or request.person.function_set.filter(committee__abbreviation='WWW',
                                                                        end__isnull=True).exists() or (
            obj.educational and request.person.function_set.filter(committee__abbreviation='OnderwijsCommissie',
                                                                   end__isnull=True).exists())):
        if request.method == "POST":
            obj.delete()
            return HttpResponseRedirect("/")
        return render(request, 'page_delete.html', {'obj': obj})
    return render(request, '403.html')

@require_committee('WWW')
def page_new(request):
    form = PageForm() if request.method != "POST" else PageForm(request.POST)
    is_new = True

    if request.method == "POST" and form.is_valid():
        page_obj = form.save()
        return HttpResponseRedirect(page_obj.get_absolute_url())

    return render(request, 'page_form.html', {
        'form': form,
        'is_new': is_new
    })


def pages(request):
    pages_list = Page.objects.all()
    return render(request, 'pages.html', {
        'pages': pages_list,
    })
