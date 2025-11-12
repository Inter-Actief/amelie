from django.forms.renderers import DjangoTemplates


class AmelieFormRenderer(DjangoTemplates):
    form_template_name = "style/forms/div.html"
    field_template_name = "style/forms/field.html"

    def render(self, template_name, context, request = None):
        # Override the default template used to render errors. This template is determined by a different class,
        # so we intercept the call in the render function itself.
        if template_name == "django/forms/errors/list/default.html":
            template_name = "style/forms/errors.html"
        return super().render(template_name=template_name, context=context, request=request)


def inject_style(*args):
    """
    Empty method. Was previously used to inject our styling into forms but is unused now.
    Stubbed out here because it's a pain to find and remove all usages.
    """
    return
