from typing import Optional
from pathlib import Path

from django import forms
from django.core.validators import FileExtensionValidator
from django.db import transaction
from django.utils.translation import gettext_lazy as _l

from amelie.files.models import GMMDocument
from amelie.gmm.models import GMM
from amelie.members.models import Person
from amelie.tools.forms import MultipleFileField


class GMMAdminForm(forms.ModelForm):
    class Meta:
        model = GMM
        fields = ("date", "agenda")

    documents = MultipleFileField(label=_l("Add documents"), required=False)

    def clean_documents(self):
        """Make sure only PDFs can be uploaded."""
        for upload in self.files.getlist("documents"):
            # FileExtensionValidator raises ValidationError if an extension is not allowed
            FileExtensionValidator(allowed_extensions=["pdf"])(upload)

    def save_documents(self, gmm: GMM, uploader: Optional[Person]):
        """Process each uploaded document."""
        with transaction.atomic():
            for upload in self.files.getlist("documents"):
                # By default, pick the filename as the caption
                caption = None
                if upload.name:
                    caption = Path(upload.name).stem
                # Create the document and add it to the GMM
                document = GMMDocument(
                    file=upload,
                    caption=caption,
                    uploader=uploader,
                    gmm=gmm
                )
                document.save()
            # Save documents to GMM
            gmm.save()
