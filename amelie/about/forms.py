from django import forms

from amelie.style.forms import inject_style
from amelie.about.models import Page


class PageForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = ['name_nl', 'name_en', 'educational', 'content_nl', 'content_en']


inject_style(PageForm)
