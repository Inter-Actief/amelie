import json
from difflib import unified_diff

from auditlog.models import LogEntry
from django import template
from django.utils.encoding import smart_str
from django.utils.translation import gettext_lazy as _l

register = template.Library()


@register.filter()
def action_string(obj):
    return _l(LogEntry.Action.choices[obj.action][1])


@register.filter()
def changes_short(obj):
    if obj.action == 2:
        return 'deleted'  # delete
    if isinstance(obj.changes, str):
        changes = json.loads(obj.changes)
    else:
        changes = obj.changes
    s = '' if len(changes) == 1 else 's'
    fields = ', '.join(changes.keys())
    if len(fields) > 75:
        i = fields.rfind(' ', 0, 75)
        fields = fields[:i] + ' ..'
    return '%d change%s: %s' % (len(changes), s, fields)


@register.filter()
def get_url(obj):
    # Get the actual object from the LogEntry and try to get its absolute URL
    actual_obj = obj.content_type.model_class().objects.get(pk=obj.object_pk)
    try:
        return actual_obj.get_absolute_url()
    except AttributeError:
        pass
    return ""


@register.filter()
def diff_string(obj):
    if obj.action == 2:  # deleted
        return '<p>{}</p>'.format(_l("This object has been removed."))
    if isinstance(obj.changes, str):
        changes = json.loads(obj.changes)
    else:
        changes = obj.changes
    changes_concat = []
    for i, field in enumerate(sorted(changes), 1):
        before, after = ['***', '***'] if field == 'password' else changes[field]
        before = ["{}\n".format(x) for x in before.split("\n")]
        after = ["{}\n".format(x) for x in after.split("\n")]
        diff_data = list(unified_diff(
            before, after, fromfile="{}".format(field), tofile="{}".format(field)
        ))
        changes_concat.append("".join(diff_data))
    return "\n".join(changes_concat)


@register.filter()
def changes_list(obj):
    if obj.action == 2:  # deleted
        return '<p>{}</p>'.format(_l("This object has been removed."))

    changes = obj.changes_dict
    append = ""
    changes_to_show = 3

    changes = list(changes.items())
    changes.sort(key=lambda x: x[0])

    if len(changes) > changes_to_show:
        more_changes = len(changes) - changes_to_show
        append = "<p>{}</p>".format(_l("And {} other changes".format(more_changes)))
        changes = changes[:changes_to_show]

    separator = smart_str(' \u2192 ')
    changes_msg = "".join(["<dt><b>{}</b></dt>"
                           "<dd>{:.50}{}{}{:.50}{}</dd>".format(field,
                                                                change[0], "..." if len(change[0]) > 50 else "",
                                                                separator,
                                                                change[1], "..." if len(change[1]) > 50 else ""
                                                                ) for field, change in changes])

    return "<dl>{}</dl>{}".format(changes_msg, append)


@register.filter()
def full_classname(obj):
    return "{}.{}".format(obj.content_type.app_label, obj.content_type.model)


@register.filter()
def actual(obj):
    try:
        return obj.content_type.model_class().objects.get(pk=obj.object_pk)
    except obj.content_type.model_class().DoesNotExist:
        return obj.object_repr
