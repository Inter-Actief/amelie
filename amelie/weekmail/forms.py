from datetime import timedelta

from django.forms import ModelForm, ModelMultipleChoiceField, CheckboxSelectMultiple
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from amelie.calendar.models import Event
from amelie.news.models import NewsItem
from amelie.weekmail.models import WeekMail


class WeekMailForm(ModelForm):
    new_activities = ModelMultipleChoiceField(required=False, queryset=Event.objects.filter(end__gte=timezone.now()), widget=CheckboxSelectMultiple,
                                              label=_("New events"), help_text=_("Only activities in the future are shown."))
    news_articles = ModelMultipleChoiceField(required=False, queryset=NewsItem.objects.filter(publication_date__gte=(timezone.now() - timedelta(days=31))), widget=CheckboxSelectMultiple,
                                             label=_("News articles"),
                                             help_text=_("Only news articles of at most 31 days ago are shown, so it is possible that no articles are shown."))

    class Meta:
        model = WeekMail
        fields = ['new_activities', 'news_articles', 'mailtype']

    def __init__(self, *args, **kwargs):
        super(WeekMailForm, self).__init__(*args, **kwargs)
        if self.instance.pk and self.instance.creation_date:
            self.fields['new_activities'].queryset = Event.objects.filter(end__gte=self.instance.creation_date)
            self.fields['news_articles'].queryset = NewsItem.objects.filter(publication_date__gte=(self.instance.creation_date - timedelta(days=31)))
