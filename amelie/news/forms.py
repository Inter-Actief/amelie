from django import forms
from django.utils.translation import gettext_lazy as _l

from amelie.news.models import NewsItem
from amelie.members.models import Committee


class NewsItemForm(forms.ModelForm):

    introduction_nl = forms.CharField(max_length=175, label=_l('Introduction'), help_text=_l('This text can be lay-outed in 175 characters (<a href="https://daringfireball.net/projects/markdown/syntax">markdown</a>)'), widget=forms.Textarea)
    introduction_en = forms.CharField(max_length=175, label=_l('Introduction'), help_text=_l('This text can be lay-outed in 175 characters (<a href="https://daringfireball.net/projects/markdown/syntax">markdown</a>)'), widget=forms.Textarea, required=False)
#    content = forms.CharField(label=_('Content'), widget=TextEditor)
    publisher = forms.ModelChoiceField(Committee.objects.all(), label=_l('Publisher'))

    class Meta:
        model = NewsItem
        fields = ["title_nl", "title_en", "introduction_nl", "introduction_en", "content_nl", "content_en",
                  "publisher", ]


class NewsItemBoardForm(NewsItemForm):

    class Meta:
        model = NewsItem
        fields = ["title_nl", "title_en", "introduction_nl", "introduction_en", "content_nl", "content_en", "publisher",
                  "pinned", ]
