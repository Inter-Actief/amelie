from django.db import models
from django.db.models.query import QuerySet


class SubclassingQuerySet(QuerySet):
    def __getitem__(self, k):
        result = super(SubclassingQuerySet, self).__getitem__(k)
        if isinstance(result, models.Model):
            return result.as_leaf_class()
        else:
            return result

    def __iter__(self):
        for item in super(SubclassingQuerySet, self).__iter__():
            if isinstance(item, models.Model):
                yield item.as_leaf_class()
            else:
                yield item


class SubclassManager(models.Manager):
    def get_queryset(self):
        return SubclassingQuerySet(self.model)


class PublicManagerMixin(object):
    def filter_public(self, request_or_bool):
        """
        Filters events that have public=false according to the request or a condition
        """

        if type(request_or_bool) == bool:
            only_public = request_or_bool
        else:
            request = request_or_bool
            only_public = not hasattr(request, 'user') or not request.user.is_authenticated

        if only_public:
            return self.filter(public=True)
        else:
            return self.all()

    def only_public(self):
        """
        Filters events that have public=false
        """
        return self.filter(public=True)
