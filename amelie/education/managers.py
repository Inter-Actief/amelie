from django.db import models

from amelie.calendar.managers import EventManager


class ComplaintCommentManager(models.Manager):
    def public(self):
        return self.filter(public=True)


class EducationEventManager(EventManager):
    def filter_public(self, request_or_bool):
        if type(request_or_bool) == bool:
            public_only = request_or_bool
        else:
            request = request_or_bool
            public_only = not hasattr(request, 'is_education_committee') or not request.is_education_committee

        if public_only:
            return self.filter(public=True)
        else:
            return self.all()
