from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='form_bootstrapify', is_safe=True)
def form_bootstrapify(formfield_html, options=""):
    try:
        label_txt = str(formfield_html.label)
    except AttributeError:
        label_txt = ""

    formfield_html = str(formfield_html)
    if any(["type=\"{}\"".format(x) in formfield_html for x in ["text", "url", "email"]]) or \
            any(["</{}>".format(x) in formfield_html for x in ["textarea", "select"]]):
        if "noclass" not in options.split(','):
            if "class=\"" in formfield_html:
                formfield_html = formfield_html.replace("class=\"", "class=\"form-control ")
            elif "class='" in formfield_html:
                formfield_html = formfield_html.replace("class='", "class='form-control ")
            else:
                formfield_html = formfield_html.replace("id=", "class=\"form-control\" id=")
        if "noplaceholder" not in options.split(','):
            formfield_html = formfield_html.replace("id=", "placeholder=\"{}\" id=".format(label_txt))

    return mark_safe(formfield_html)


@register.filter(name='form_chosenify', is_safe=True)
def form_chosenify(formfield_html, options=""):
    formfield_html = str(formfield_html)
    if "</select>" in formfield_html:
        if "noclass" not in options.split(','):
            if "class=\"" in formfield_html:
                formfield_html = formfield_html.replace("class=\"", "class=\"chosen-select ")
            elif "class='" in formfield_html:
                formfield_html = formfield_html.replace("class='", "class='chosen-select ")
            else:
                formfield_html = formfield_html.replace("id=", "class=\"chosen-select\" id=")

    return mark_safe(formfield_html)
