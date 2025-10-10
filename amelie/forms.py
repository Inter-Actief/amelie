from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _l
from django.core.validators import FileExtensionValidator

from amelie.style.forms import inject_style
from amelie.tools.forms import MultipleFileField

class AmelieAuthenticationForm(AuthenticationForm):
    remain_logged_in = forms.BooleanField(required=False, label=_l('Stay logged in'))


class ProfilePictureUploadForm(forms.Form):
    profile_picture = MultipleFileField()

    def clean_photo_files(self):
        allowed_extensions = ["jpg", "jpeg", "gif"]
        for file in self.files.getlist('photo_files'):
            # FileExtensionValidator raises ValidationError if an extension is not allowed
            FileExtensionValidator(allowed_extensions=allowed_extensions)(file)


class ProfilePictureVerificationFrom(forms.Form):
    is_verified = forms.BooleanField(initial=False, required=False, label=_l('Verify'))
    id = forms.IntegerField(widget=forms.HiddenInput())

inject_style(ProfilePictureVerificationFrom, ProfilePictureUploadForm, AmelieAuthenticationForm)
