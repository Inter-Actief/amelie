import logging
from enum import StrEnum
from typing import List, Dict, Any, Optional, NamedTuple

import requests
from django.conf import settings
from django.utils import translation
from django.utils.html import strip_tags
from django.utils.translation import gettext as _, gettext
from documenso_sdk import Documenso, \
    EnvelopeCreatePayloadTypedDict, EnvelopeCreateVisibility, EnvelopeCreateFileTypedDict, EnvelopeCreateResponse, \
    EnvelopeCreateRecipientTypedDict, EnvelopeCreateMetaTypedDict, EnvelopeCreateDateFormat, \
    EnvelopeCreateEmailSettingsTypedDict, EnvelopeCreateLanguage, EnvelopeCreateRole, EnvelopeDistributeResponse, \
    EnvelopeCreateType, EnvelopeGetStatus, EnvelopeItemDownloadVersion

FIELD_TEMPLATES = {
    "MEMBERSHIP": [
        {"type": "SIGNATURE", "positionX": 3.75, "positionY": 83.75, "width": 43, "height": 13.5}
    ],
    "AUTHORIZATION": [
        {"type": "SIGNATURE", "positionX": 3.75, "positionY": 83.75, "width": 43, "height": 13.5}
    ],
}

LANGUAGE_MAP = {
    'en': EnvelopeCreateLanguage.EN,
    'nl': EnvelopeCreateLanguage.NL,
}

def get_documenso_instance() -> Documenso:
    return Documenso(
        api_key=settings.DOCUMENSO_SETTINGS.get('API_KEY'),
        server_url=settings.DOCUMENSO_SETTINGS.get('API_BASE'),
    )


class DocumensoFieldTemplate(StrEnum):
    MEMBERSHIP = "MEMBERSHIP"
    AUTHORIZATION = "AUTHORIZATION"


class DocumensoRecipient(NamedTuple):
    email: str
    name: str


class DocumensoFile(NamedTuple):
    filename: str
    data: bytes
    field_template_per_page: List[DocumensoFieldTemplate]

class RetrievedFile(NamedTuple):
    filename: str
    data: bytes


def create_document(
    title: str,
    files: List[DocumensoFile],
    language: EnvelopeCreateLanguage,
    subject: str,
    message: str,
    sign_recipients: Optional[List[DocumensoRecipient]] = None,
    approve_recipients: Optional[List[DocumensoRecipient]] = None,
    cc_recipients: Optional[List[DocumensoRecipient]] = None,
    email_reply_to: Optional[str] = None,
    email_settings: Optional[EnvelopeCreateEmailSettingsTypedDict] = None,
    amelie_reference: Optional[str] = None,
    documenso_folder_id: Optional[str] = None
) -> EnvelopeCreateResponse:
    if sign_recipients is None:
        sign_recipients = []
    if approve_recipients is None:
        approve_recipients = []
    if cc_recipients is None:
        cc_recipients = []

    # Configure default email settings if not given
    if email_settings is None:
        email_settings = EnvelopeCreateEmailSettingsTypedDict(
            recipient_signing_request=True,  # Email recipients with a signing request
            recipient_removed=True,  # Email recipients when they're removed from a pending document
            recipient_signed=False,  # Do not email the owner when a recipient signs
            document_pending=False,  # Do not email the signer if the document is still pending
            document_completed=True,  # Email recipients when the document is completed
            document_deleted=True,  # Email recipients when a pending document is deleted
            owner_document_completed=False,  # Do not email the owner when the document is completed
        )

    with get_documenso_instance() as doc:
        # Build files and fields
        doc_files: List[EnvelopeCreateFileTypedDict] = []
        doc_fields: List[Dict[str, Any]] = []

        for file_number, file in enumerate(files, start=0):
            doc_files.append(EnvelopeCreateFileTypedDict(file_name=file.filename, content=file.data))
            # Build fields list for this file
            for page_number, field_template_name in enumerate(file.field_template_per_page, start=1):
                fields_this_page = FIELD_TEMPLATES.get(field_template_name.value, []).copy()
                # Add the pageNumber
                for f in fields_this_page:
                    f['identifier'] = file_number
                    f['page'] = page_number
                doc_fields.extend(fields_this_page)

        # Build recipients list
        doc_recipients: List[EnvelopeCreateRecipientTypedDict] = []
        # Add regular signing recipients
        for r in sign_recipients:
            doc_recipients.append(EnvelopeCreateRecipientTypedDict(
                email=r.email,
                name=r.name,
                role=EnvelopeCreateRole.SIGNER,
                fields=doc_fields,
            ))
        # Add approver recipients
        for r in approve_recipients:
            doc_recipients.append(EnvelopeCreateRecipientTypedDict(
                email=r.email,
                name=r.name,
                role=EnvelopeCreateRole.APPROVER
            ))
        # Add CC recipients
        for r in cc_recipients:
            doc_recipients.append(EnvelopeCreateRecipientTypedDict(
                email=r.email,
                name=r.name,
                role=EnvelopeCreateRole.CC
            ))

        # Build the metadata
        doc_meta = EnvelopeCreateMetaTypedDict(
            subject=subject,
            message=message,
            timezone=settings.TIME_ZONE,
            language=language,
            date_format=EnvelopeCreateDateFormat.YYYY_M_MDD_H_HMM,
            email_reply_to=email_reply_to,
            email_settings=email_settings
        )

        # Prepare payload arguments
        payload_kwargs = {
            "title": title,
            "type": EnvelopeCreateType.DOCUMENT,
            "visibility": EnvelopeCreateVisibility.MANAGER_AND_ABOVE,
            "recipients": doc_recipients,
            "meta": doc_meta,
        }
        if amelie_reference is not None:
            payload_kwargs['external_id'] = amelie_reference
        if documenso_folder_id is not None:
            payload_kwargs['folder_id'] = documenso_folder_id

        # Create the document in Documenso
        return doc.envelopes.create(
            payload=EnvelopeCreatePayloadTypedDict(**payload_kwargs),
            files=doc_files
        )


def send_document(envelope_id) -> EnvelopeDistributeResponse:
    with get_documenso_instance() as doc:
        return doc.envelopes.distribute(envelope_id=envelope_id)


def retrieve_documents(envelope_id) -> List[RetrievedFile]:
    with get_documenso_instance() as doc:
        envelope_info = doc.envelopes.get(envelope_id=envelope_id)
        if envelope_info.status != EnvelopeGetStatus.COMPLETED:
            raise ValueError(gettext("Requested documents of envelope {envelope_id} but this document is not completed yet.").format(envelope_id=envelope_id))

        documents = []
        for item in envelope_info.envelope_items:
            # The SDK method `doc.envelopes.items.download` doesn't like to download files (it's autogenerated and expects JSON)
            # so we have to manually build the request for this one.
            api_base = settings.DOCUMENSO_SETTINGS.get("API_BASE")
            document = requests.get(
                url=f"{api_base}/envelope/item/{item.id}/download?version=signed",
                headers={"Authorization": settings.DOCUMENSO_SETTINGS.get("API_KEY", "")},
            )
            documents.append(RetrievedFile(filename=item.title, data=document.content))
    return documents


def create_enrollment_document():
    raise NotImplementedError()


def create_membership_document(membership) -> EnvelopeCreateResponse:
    from amelie.members.models import Membership
    membership: Membership

    with translation.override(membership.member.preferred_language):
        return create_document(
            title=_("Membership form #{id} for {name}").format(id=membership.pk, name=membership.member.incomplete_name()),
            files=[
                DocumensoFile(
                    filename=f"membership_form_{membership.member.slug}_{membership.pk}.pdf",
                    data=membership.get_as_pdf(),
                    field_template_per_page=[DocumensoFieldTemplate.MEMBERSHIP]  # One page with the membership details
                )
            ],
            language=LANGUAGE_MAP.get(membership.member.preferred_language, EnvelopeCreateLanguage.EN),
            subject=_("[Inter-Actief] Please sign your membership documents"),
            message=_(
                "Dear {name},\n"
                "\n"
                "We please request you to sign your membership form.\n"
                "By signing this membership form, you agree to all terms of membership of the bylaws and the Rules and Regulations of this association.\n"
                "If you have any questions about this message, please contact the board via e-mail on board@inter-actief.net\n"
                "\n"
                "Kind regards,\n"
                "I.C.T.S.V. Inter-Actief\n"
                "---\n"
                "This message was automatically generated by the Inter-Actief website, contact the board if you have any questions."
            ).format(name=membership.member.incomplete_name()),
            sign_recipients=[DocumensoRecipient(name=membership.member.incomplete_name(), email=membership.member.email_address)],
            cc_recipients=[DocumensoRecipient(name=c[0], email=c[1]) for c in settings.DOCUMENSO_SETTINGS.get('DOCUMENT_SETTINGS', {}).get('MEMBERSHIP', {}).get('CC_CONTACTS', [])],
            # Comma-separated encoded string containing the object type and ID.
            # We encode this information here to be able to trace back which document is for which object.
            # I.E. 'AML:MEM:14' = Amelie Membership #14.
            amelie_reference=f"AML:MEM:{membership.pk}",
            documenso_folder_id=settings.DOCUMENSO_SETTINGS.get('DOCUMENT_SETTINGS', {}).get('MEMBERSHIP', {}).get('DOCUMENSO_FOLDER_ID', None),
            email_reply_to=settings.DOCUMENSO_SETTINGS.get('DOCUMENT_SETTINGS', {}).get('AUTHORIZATION', {}).get('REPLY_TO', None)
        )


def create_authorization_document(authorization) -> EnvelopeCreateResponse:
    from amelie.personal_tab.models import Authorization
    authorization: Authorization

    with translation.override(authorization.person.preferred_language):
        authorization_text_plain = str(authorization.authorization_type.text)
        authorization_text_plain = authorization_text_plain.replace("</br>", "\n")
        authorization_text_plain = authorization_text_plain.replace("<br>", "\n")
        authorization_text_plain = strip_tags(authorization_text_plain)

        return create_document(
            title=_("Mandate form #{id} for {name}").format(id=authorization.pk, name=authorization.person.incomplete_name()),
            files=[
                DocumensoFile(
                    filename=f"mandate_form_{authorization.person.slug}_{authorization.pk}.pdf",
                    data=authorization.get_as_pdf(),
                    field_template_per_page=[DocumensoFieldTemplate.AUTHORIZATION]  # One page with the mandate details
                )
            ],
            language=LANGUAGE_MAP.get(authorization.person.preferred_language, EnvelopeCreateLanguage.EN),
            subject=_("[Inter-Actief] Please sign your direct debit authorization"),
            message=_(
                "Dear {name},\n"
                "\n"
                "We please request you to sign your direct debit authorization form.\n"
                "{authorization_text}\n"
                "If you have any questions about this message, please contact the board via e-mail on board@inter-actief.net\n"
                "\n"
                "Kind regards,\n"
                "I.C.T.S.V. Inter-Actief\n"
                "---\n"
                "This message was automatically generated by the Inter-Actief website, contact the board if you have any questions."
            ).format(name=authorization.person.incomplete_name(), authorization_text=authorization_text_plain),
            sign_recipients=[DocumensoRecipient(name=authorization.person.incomplete_name(), email=authorization.person.email_address)],
            cc_recipients=[DocumensoRecipient(name=c[0], email=c[1]) for c in settings.DOCUMENSO_SETTINGS.get('DOCUMENT_SETTINGS', {}).get('AUTHORIZATION', {}).get('CC_CONTACTS', [])],
            # Comma-separated encoded string containing the object type and ID.
            # We encode this information here to be able to trace back which document is for which object.
            # I.E. 'AML:MDT:14' = Amelie Authorization #14.
            amelie_reference=f"AML:MDT:{authorization.pk}",
            documenso_folder_id=settings.DOCUMENSO_SETTINGS.get('DOCUMENT_SETTINGS', {}).get('AUTHORIZATION', {}).get('DOCUMENSO_FOLDER_ID', None),
            email_reply_to=settings.DOCUMENSO_SETTINGS.get('DOCUMENT_SETTINGS', {}).get('AUTHORIZATION', {}).get('REPLY_TO', None)
        )
