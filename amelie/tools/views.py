import logging
import random

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import get_template, render_to_string
from django.utils import translation
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from django.views.generic import ListView
from django.views.generic.base import TemplateView

from amelie.iamailer.mailer import render_mail
from amelie.tools.color_palette_generator import generate_palette
from amelie.tools.decorators import require_superuser
from amelie.tools.forms import MailTemplateTestForm, ExportTypeSelectForm
from amelie.tools.mail import person_dict
from amelie.tools.mixins import RequireSuperuserMixin, RequireBoardMixin
from amelie.tools.models import DataExportInformation


@require_superuser
def logging_config(request):
    """
    Display the current logging configuration.
    """

    rootlogger = logging.getLogger()

    manager = rootlogger.manager

    d = manager.loggerDict

    keys = list(d.keys())
    keys.sort()

    loggers = {}

    for k in keys:
        logger = d[k]
        if not isinstance(logger, logging.PlaceHolder):
            loggers[k] = logger

    handlers = set([handler for logger in loggers.values() for handler in logger.handlers])

    keys = list(loggers.keys())
    keys.sort()

    logger_list = []

    for k in keys:
        logger = loggers[k]
        logger_list.append(logger)

    return render(request, 'tools_logging_config.html', locals())


@require_superuser
def flash(request):
    """
    Display some flash messages for debugging purposes.
    """

    messages.debug(request, 'Some SQL statements were executed.')
    messages.info(request, 'Three credits remain in your account.')
    messages.success(request, 'Profile details updated.')
    messages.warning(request, 'Your account expires in three days.')
    messages.error(request, 'Document deleted.')

    return render(request, 'tools_logging_config.html')


class MailPreview(RequireSuperuserMixin, TemplateView):
    template_name = "weekmail/weekmail_preview.html"

    def render_to_response(self, context, **response_kwargs):
        template = get_template(context.get("template_name", "iamailer/testmail.mail"))

        old_language = translation.get_language()
        if self.kwargs.get("lang", False):
            translation.activate(self.kwargs["lang"])

        try:
            content, subject, attachments = render_mail(template=template, html=True, preview=True)
        finally:
            translation.activate(old_language)

        context['content'] = content

        return super(MailPreview, self).render_to_response(context, **response_kwargs)

    def get_context_data(self, **kwargs):
        context = super(MailPreview, self).get_context_data(**kwargs)
        context['preview'] = True
        return context


@require_superuser
def mail_template_test(request):
    if request.POST:
        form = MailTemplateTestForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data
            template = get_template(data['template'])

            old_language = translation.get_language()
            translation.activate(data['language'])

            html = data['format'] == 'html'

            mail_context = {'recipient': person_dict(request.person)}

            try:
                content, subject, attachments = render_mail(template=template, context=mail_context, html=html,
                                                            preview=True)
            finally:
                translation.activate(old_language)

            context = {'content': content}

            if html:
                return render(request, 'weekmail/weekmail_preview.html', context)
    else:
        form = MailTemplateTestForm()

    return render(request, 'tools_mailtemplatetest.html', locals())


class DataExportStatistics(RequireBoardMixin, ListView):
    model = DataExportInformation
    template_name = "data_export_statistics.html"
    paginate_by = 100
    ordering = '-id'

    def get_queryset(self):
        qs = self.model.objects.all()
        export_type = self.request.GET.get('export_type', '')

        if export_type:
            qs = qs.filter(export_type=export_type)

        return qs.order_by(self.ordering)

    def get_context_data(self, **kwargs):
        context = super(DataExportStatistics, self).get_context_data(**kwargs)
        context['model'] = self.model
        context['export_types_form'] = ExportTypeSelectForm(self.request.GET)
        return context

@cache_page(60 * 15)  # Cache colors for 15 minutes
@vary_on_cookie  # Different cache for each user/browser/session
def color_scheme(request):
    h = random.randint(0, 359)  # Any hue is fine
    s = random.randint(50, 100)  # Make sure saturation is in the upper half (we want at least semi-vibrant colors)
    l = random.randint(20, 70)  # Make sure the lightness is in the middle half (we want to generate lighter and darker variant colors)
    palette = generate_palette(h=h, s=s, l=l, shade_variation=30)
    return HttpResponse(
        render_to_string(template_name="tools/color_scheme.css", context={"palette": palette}, request=request),
        content_type='text/css',
    )
