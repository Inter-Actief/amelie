from django import template
from django.urls import reverse
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

from amelie.claudia.models import Mapping, SharedDrive
from amelie.claudia.tools import is_valid_email

register = template.Library()


def _css_class(obj):
    """ Get CSS Class for alias, email, Mapping or mapable object. """
    if not obj:
        cls = ''

    elif isinstance(obj, str):
        # Alias or e-mail
        if is_valid_email(obj):
            cls = 'claudia-email'
        else:
            cls = 'claudia-error'

    elif isinstance(obj, Mapping):
        cls = 'claudia-%s' % obj.type
        if not obj.active:
            cls = 'claudia-inactive %s' % cls

    elif isinstance(obj, SharedDrive):
        cls = 'claudia-%s' % Mapping.get_type(obj)

    else:
        cls = 'claudia-%s' % Mapping.get_type(obj)
        if not obj.is_active():
            cls = 'claudia-inactive %s' % cls

    return cls


@register.filter()
def clau_class(obj):
    """ Get CSS Class for alias, email, Mapping or mapable object. """
    return mark_safe(_css_class(obj))


@register.filter(needs_autoescape=True)
def clau_link(obj, text='', autoescape=None):
    if autoescape:
        esc = conditional_escape
    else:
        esc = lambda x: x

    if not obj:
        return mark_safe('&mdash;')

    if isinstance(obj, str):
        url = reverse('claudia:email_detail', kwargs={'email': obj})
    else:
        url = obj.get_absolute_url()

    if isinstance(obj, str):
        name = obj
    elif isinstance(obj, Mapping):
        name = obj.name
    else:
        name = obj.get_name()

    cls = _css_class(obj)
    text = text or name

    if url:
        result = '<a class="%s" href="%s">%s</a>' % (cls, esc(url), esc(text))
    else:
        result = '<span class="%s">%s</span>' % (cls, esc(text))

    return mark_safe(result)


@register.filter(needs_autoescape=True)
def clau_mapping(obj, text='', autoescape=None):
    if autoescape:
        esc = conditional_escape
    else:
        esc = lambda x: x

    if not obj:
        return mark_safe('&mdash;')

    if isinstance(obj, Mapping):
        mp = obj
    else:
        mp = Mapping.find(obj)

    if mp:
        url = mp.get_absolute_url()
        cls = _css_class(mp)
        name = mp.name
    else:
        url = reverse('claudia:mapping_find', kwargs={'obj_type': Mapping.get_type(obj), 'ident': obj.id})
        cls = 'claudia-nomapping'
        name = obj.get_name()

    text = text or name

    result = '<a class="%s" href="%s">%s</a>' % (cls, esc(url), esc(text))
    return mark_safe(result)


@register.filter(needs_autoescape=True)
def clau_account(account, autoescape=None):
    if autoescape:
        esc = conditional_escape
    else:
        esc = lambda x: x

    if not account:
        return mark_safe('&mdash;')

    cls = 'claudia-account'

    result = '<span class="%s">%s</span>' % (cls, esc(account))
    return mark_safe(result)


@register.filter(needs_autoescape=True)
def clau_kanidm(obj, text='', autoescape=None):
    if autoescape:
        esc = conditional_escape
    else:
        esc = lambda x: x

    if not obj:
        return mark_safe('&mdash;')

    if isinstance(obj, Mapping):
        mp = obj
    else:
        mp = Mapping.find(obj)

    if not mp or not mp.kanidm_id:
        return mark_safe('&mdash;')

    url = ""
    cls = ""
    if mp.is_person():
        url = reverse('claudia:kanidm_person_detail', kwargs={'uuid': mp.kanidm_id})
        cls = "icon icon-user"
    elif mp.is_group():
        url = reverse('claudia:kanidm_group_detail', kwargs={'uuid': mp.kanidm_id})
        cls = "icon icon-group"

    if not url:
        return mark_safe('&mdash;')

    result = f'<a class="{cls}" href="{esc(url)}">{esc(mp.kanidm_id)}</a>'
    return mark_safe(result)


@register.filter(needs_autoescape=True)
def clau_editlinks(obj, autoescape=None):
    if autoescape:
        esc = conditional_escape
    else:
        esc = lambda x: x

    if not obj:
        return ''

    editlink = ''  # TODO '<a class="icon icon-pencil" href="#">edit</a>'

    deleteurl = reverse('claudia:link_delete', kwargs={'link_id': obj.id})
    deletelink = '<a class="icon icon-delete" href="%s">delete</a>' % (deleteurl, )

    result = '%s %s' % (editlink, deletelink)
    return mark_safe(result)
