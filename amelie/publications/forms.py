from django import forms

from amelie.activities.forms import DateTimeSelector, SplitDateTimeField
from .models import Publication


class PublicationForm(forms.ModelForm):
    class Meta:
        model = Publication
        fields = ('name', 'publication_type', 'date_published', 'file', 'thumbnail', 'public', 'is_featured',)
        field_classes = {'date_published': SplitDateTimeField, }
        widgets = {'date_published': DateTimeSelector, }
