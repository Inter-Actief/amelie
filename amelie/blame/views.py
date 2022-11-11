from django.contrib.contenttypes.models import ContentType
from django.views.generic import DetailView
from django.views.generic import ListView

from auditlog.models import LogEntry

from amelie.tools.mixins import RequireBoardMixin


class BlameOverview(RequireBoardMixin, ListView):
    model = LogEntry
    template_name = "blame/overview.html"
    paginate_by = 50

    def get_queryset(self):
        content_types = list(set([x['content_type'] for x in LogEntry.objects.all().values('content_type')]))
        return ContentType.objects.filter(pk__in=content_types).order_by('app_label', 'model')


class BlameModelOverview(RequireBoardMixin, ListView):
    model = LogEntry
    template_name = "blame/model_overview.html"
    paginate_by = 50

    def get_context_data(self, **kwargs):
        context = super(BlameModelOverview, self).get_context_data(**kwargs)
        ctype_id = self.kwargs.get("content_type", None)
        if ctype_id is not None:
            ctype = ContentType.objects.get(pk=ctype_id)
            context['modelname'] = "{}.{}".format(ctype.app_label, ctype.model)
        else:
            context['modelname'] = None

        return context

    def get_queryset(self):
        ctype_id = self.kwargs.get('content_type', None)
        if ctype_id is not None:
            return LogEntry.objects.filter(content_type=ctype_id)
        else:
            raise ValueError("No content type ID given.")


class BlameObjectDetail(RequireBoardMixin, DetailView):
    model = LogEntry
    template_name = "blame/blame_detail.html"

    def get_context_data(self, **kwargs):
        context = super(BlameObjectDetail, self).get_context_data(**kwargs)

        ctype = self.object.content_type

        context['content_type_id'] = ctype.pk
        context['modelname'] = "{}.{}".format(ctype.app_label, ctype.model)

        return context


class BlameObjectChangelog(RequireBoardMixin, ListView):
    model = LogEntry
    template_name = "blame/blame_changelog.html"
    paginate_by = 50

    def get_context_data(self, **kwargs):
        context = super(BlameObjectChangelog, self).get_context_data(**kwargs)
        ctype_id = self.kwargs.get("content_type", None)
        object_pk = self.kwargs.get('object_pk', None)

        if ctype_id is None or object_pk is None:
            raise ValueError("No content type ID or object ID given.")

        ctype = ContentType.objects.get(pk=ctype_id)

        # filter().first() returns none if nothing is found (e.g. object has been removed)
        obj = ctype.model_class().objects.filter(pk=object_pk).first()

        context['content_type_id'] = ctype_id
        context['modelname'] = "{}.{}".format(ctype.app_label, ctype.model)
        context['objectname'] = str(obj) if obj else self.object_list.latest().object_repr

        return context

    def get_queryset(self):
        ctype_id = self.kwargs.get("content_type", None)
        object_pk = self.kwargs.get('object_pk', None)

        if ctype_id is None or object_pk is None:
            raise ValueError("No content type ID or object ID given.")

        return LogEntry.objects.filter(content_type=ctype_id, object_pk=object_pk)
