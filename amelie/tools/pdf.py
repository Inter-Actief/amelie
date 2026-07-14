from PIL import Image
from django.conf import settings
from django.utils import timezone, translation
from django.utils.encoding import force_str
from django.utils.translation import gettext as _
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from amelie.members.models import Person, UnverifiedEnrollment
from amelie.personal_tab.models import Authorization


def pdf_separator_page(canvas, text):
    # Generates an empty page with only the given text on it.
    canvas.setTitle(_("Separator page"))
    width, height = A4
    canvas.setFont("Helvetica-Bold", 34)
    canvas.drawString(60, height - 140, text)
    # Inter-Actief logo
    # Original: 1198*226
    canvas.drawInlineImage(Image.open('%s/amelie/style/static/img/pdf/inter-actief.png' % settings.BASE_PATH),
                           x=width - 25 - 240,
                           y=height - 25 - 45,
                           width=240,
                           height=45)
    canvas.showPage()


def pdf_enrollment_form(file, person, membership, signing_date=None):
    with translation.override(person.preferred_language):
        c = canvas.Canvas(file, pagesize=A4)
        pdf_membership_page(c, person, membership, signing_date=None)
        if isinstance(person, Person):
            # Normal enrollment
            for m in person.authorization_set.all():
                pdf_authorization_page(c, m, signing_date=None)
        elif isinstance(person, UnverifiedEnrollment):
            # Unverified Pre-enrollment
            for m in person.authorizations.all():
                pdf_authorization_page(c, (m, person), signing_date=None)
        c.save()


def pdf_membership_form(file, person, membership):
    with translation.override(person.preferred_language):
        c = canvas.Canvas(file, pagesize=A4)
        pdf_membership_page(c, person, membership)
        c.save()


def pdf_authorization_form(file, authorization):
    # authorization param can be an Authorization object for regular authorizations, or
    # a tuple of (Authorization, UnverifiedEnrollment) for authorizations linked to unverified enrollments.
    if isinstance(authorization, tuple):
        person = authorization[1]
    else:
        person = authorization.person
    with translation.override(person.preferred_language):
        c = canvas.Canvas(file, pagesize=A4)
        c.setTitle(_("Mandate form"))
        pdf_authorization_page(c, authorization)
        c.save()


def pdf_membership_page(c, person, membership, signing_date=None):
    c.setTitle(_("Membership form"))

    width, height = A4

    c.setFont("Helvetica-Bold", 34)
    c.drawString(25, height - 60, _("Membership"))

    # Inter-Actief logo
    # Original: 1198*226
    c.drawInlineImage(Image.open('%s/amelie/style/static/img/pdf/inter-actief.png' % settings.BASE_PATH),
                      x=width - 25 - 240,
                      y=height - 25 - 45,
                      width=240,
                      height=45)

    h = height - 80

    c.setFont("Helvetica", 12)
    text = _("By signing this document I agree to all terms of membership of "
             "the bylaws and the Rules and Regulations of this association.")
    style = getSampleStyleSheet()['BodyText']
    style.fontSize = 12
    style.leading = 17
    p = Paragraph(text, style)
    ww, hw = p.wrap(width - 50, 100)
    p.drawOn(c, 25, h - hw - 3)
    h -= hw
    h -= 10

    h -= 15
    c.drawString(25, h, _("The following personal information will be included in the membership records:"))
    h -= 10

    c.setFont("Helvetica-Bold", 12)
    h -= 15
    c.drawString(25, h, _("Name"))
    h -= 15
    c.drawString(25, h, _("Gender"))
    h -= 15
    c.drawString(25, h, _("Birth date"))
    h -= 15
    c.drawString(25, h, _("Language of preference"))
    h -= 15
    c.drawString(25, h, _("International?"))
    h -= 10

    h -= 15
    c.drawString(25, h, _("Address"))
    h -= 15
    c.drawString(25, h, _("City"))
    h -= 15
    c.drawString(25, h, _("Country"))
    h -= 10

    h -= 15
    c.drawString(25, h, _("E-mail address"))
    h -= 15
    c.drawString(25, h, _("Phonenumber"))
    h -= 10

    h -= 15
    c.drawString(25, h, _("E-mail of parent(s)/guardian(s)"))
    h -= 15
    c.drawString(25, h, _("Address of parent(s)/guardian(s)"))
    h -= 15
    c.drawString(25, h, _("Residence of parent(s)/guardian(s)"))
    h -= 15
    c.drawString(25, h, _("Country of parent(s)/guardian(s)"))
    h -= 10

    h -= 15
    if isinstance(person, Person):
        if person.is_employee():
            c.drawString(25, h, _(u"Employee number"))
            h -= 15
        else:
            c.drawString(25, h, _("Course"))
            h -= 15
            c.drawString(25, h, _("Student number"))
    elif isinstance(person, UnverifiedEnrollment):
        # person is an UnverifiedEnrollment, which is always a student
        c.drawString(25, h, _("Course"))
        h -= 15
        c.drawString(25, h, _("Student number"))
    h -= 10

    h -= 15
    c.drawString(25, h, _("Membership"))
    h -= 15
    c.drawString(25, h, _("Preferences"))

    # Reset height
    h += 18 * 15 + 5 * 10

    # data
    c.setFont("Helvetica", 12)

    data_left = 240

    h -= 15
    c.drawString(data_left, h, person.full_name())
    h -= 15
    c.drawString(data_left, h, person.get_gender_display())
    h -= 15
    if person.date_of_birth:
        c.drawString(data_left, h, person.date_of_birth.strftime('%d-%m-%Y'))
    h -= 15
    c.drawString(data_left, h, person.get_preferred_language_display())
    h -= 15
    c.setFont("Helvetica", 10)
    c.drawString(data_left, h, person.get_international_member_display())
    c.setFont("Helvetica", 12)
    h -= 10

    h -= 15
    c.drawString(data_left, h, person.address)
    h -= 15
    c.drawString(data_left, h, '%s %s' % (person.postal_code, person.city))
    h -= 15
    c.drawString(data_left, h, person.country)
    h -= 10

    h -= 15
    c.drawString(data_left, h, person.email_address)
    h -= 15
    c.drawString(data_left, h, person.telephone)
    h -= 10

    h -= 15
    c.drawString(data_left, h, person.email_address_parents)
    h -= 15
    c.drawString(data_left, h, person.address_parents)
    h -= 15
    if person.postal_code_parents is None:
        postal_code_parents = ''
    else:
        postal_code_parents = person.postal_code_parents

    if person.city_parents is None:
        city_parents = ''
    else:
        city_parents = person.city_parents
    c.drawString(data_left, h, '%s %s' % (postal_code_parents, city_parents))
    h -= 15
    if person.country_parents is None or person.country_parents == 0:
        country_parents = ''
    else:
        country_parents = person.country_parents
    c.drawString(data_left, h, country_parents)
    h -= 10

    # Student details
    if isinstance(person, Person):
        if person.is_employee():
            h -= 15
            c.drawString(data_left, h, person.employee.employee_number())
            h -= 15
        elif hasattr(person, 'student'):
            h -= 15
            c.drawString(data_left, h, ', '.join(
                ['%s (%s)' % (s.study.abbreviation, force_str(s.dogroup) if s.dogroup else '-') for s in
                 person.student.studyperiod_set.all()]))
            h -= 15
            c.drawString(data_left, h, person.student.student_number())
        else:
            # no student details
            h -= 15
            h -= 15
    elif isinstance(person, UnverifiedEnrollment):
        if hasattr(person, 'studies'):
            h -= 15
            c.drawString(data_left, h, ', '.join(
                ['%s (%s)' % (s.abbreviation, force_str(person.dogroup) if person.dogroup else '-') for s in
                 person.studies.all()]))
            h -= 15
            c.drawString(data_left, h, str(person.student_number))
        else:
            # no student details
            h -= 15
            h -= 15

    h -= 10

    h -= 15
    if isinstance(person, Person):
        # membership is a Membership
        c.drawString(data_left, h, membership.type.name)
    elif isinstance(person, UnverifiedEnrollment):
        # membership is a MembershipType
        c.drawString(data_left, h, membership.name)

    h -= 15
    c.setFont("Helvetica", 10)
    for preference in person.preferences.filter(print=True):
        c.drawString(data_left, h, preference.preference)
        h -= 12
    else:
        # No preferences
        h -= 12

    h -= 20

    # student number barcode
    try:
        student_number = None
        if isinstance(person, Person):
            student_number = person.student.number
        elif isinstance(person, UnverifiedEnrollment):
            student_number = person.student_number

        if student_number:
            from reportlab.graphics.barcode import code128

            barcode = code128.Code128(str(student_number), barHeight=90, barWidth=2)
            barcode.drawOn(c, 325, 25)
    except Person.student.RelatedObjectDoesNotExist:
        pass

    # signature box, always at static position for digital signature.
    c.setFont("Helvetica", 12)
    if signing_date is not None:
        c.drawString(25, 145, _("Signature on %(date)s:") % {'date': signing_date.strftime('%d-%m-%Y')})
    else:
        c.drawString(25, 145, _("Signature:"))

    p = c.beginPath()
    p.moveTo(25, 135)
    p.lineTo(275, 135)
    p.lineTo(275, 25)
    p.lineTo(25, 25)
    p.lineTo(25, 135)
    c.setDash([], 0)
    c.drawPath(p)

    c.showPage()


def pdf_authorization_page(c, authorization, signing_date=None):
    width, height = A4

    h = height - 50

    c.setFont("Helvetica-Bold", 18)
    c.drawString(25, h, _("Direct debit mandate"))
    c.setFont("Helvetica-Bold", 25)
    c.drawRightString(width - 40, h - 7, _("SEPA"))
    h -= 14
    c.setFont("Helvetica-Oblique", 12)
    if isinstance(authorization, Authorization):
        c.drawString(25, h, authorization.authorization_type.name)
    elif isinstance(authorization, tuple):
        # authorization is a tuple of (Authorization, UnverifiedEnrollment)
        c.drawString(25, h, authorization[0].authorization_type.name)
    h -= 25
    h2 = h
    # IA logo
    c.drawInlineImage(Image.open('%s/amelie/style/static/img/pdf/ialogo.png' % settings.BASE_PATH),
                      33, h - 150, 150, 150)

    # Direct Debit Personal Info
    h -= 12
    w = 200
    c.setFont("Helvetica-Bold", 12)
    c.drawString(w, h, _("Creditor name"))
    c.setFont("Helvetica", 12)
    c.drawString(w + 140, h, u"I.C.T.S.V. Inter-")
    c.setFont("Helvetica-Oblique", 12)
    c.drawString(w + 224, h, u"Actief")
    h -= 22

    c.setFont("Helvetica-Bold", 12)
    c.drawString(w, h, _("Creditor address"))
    c.setFont("Helvetica", 12)
    c.drawString(w + 140, h, _(u"P.O. Box 217"))
    h -= 22

    c.setFont("Helvetica-Bold", 12)
    c.drawString(w, h, _("Creditor postal code"))
    c.setFont("Helvetica", 12)
    c.drawString(w + 140, h, u"7500 AE")
    h -= 22

    c.setFont("Helvetica-Bold", 12)
    c.drawString(w, h, _("Creditor city"))
    c.setFont("Helvetica", 12)
    c.drawString(w + 140, h, u"Enschede")
    h -= 22

    c.setFont("Helvetica-Bold", 12)
    c.drawString(w, h, _("Creditor country"))
    c.setFont("Helvetica", 12)
    c.drawString(w + 140, h, _(u"Netherlands"))
    h -= 22

    c.setFont("Helvetica-Bold", 12)
    c.drawString(w, h, _("Creditor identifier"))
    c.setFont("Helvetica", 12)
    c.drawString(w + 140, h, settings.DIRECT_DEBIT_DEBTOR_ID)
    h -= 22

    c.setFont("Helvetica-Bold", 12)
    c.drawString(w, h, _("Mandate reference"))
    c.setFont("Helvetica", 12)
    if isinstance(authorization, Authorization):
        c.drawString(w + 140, h, authorization.authorization_reference())
    elif isinstance(authorization, tuple):
        # authorization is a tuple of (Authorization, UnverifiedEnrollment)
        c.drawString(w + 140, h, authorization[0].authorization_reference())
    h -= 22

    h = h2 - 150 - 25
    style = getSampleStyleSheet()['BodyText']
    style.fontSize = 12
    style.leading = 17
    if isinstance(authorization, Authorization):
        p = Paragraph(authorization.authorization_type.text, style)
    elif isinstance(authorization, tuple):
        # authorization is a tuple of (Authorization, UnverifiedEnrollment)
        p = Paragraph(authorization[0].authorization_type.text, style)
    ww, hw = p.wrap(width - 50, 100)
    p.drawOn(c, 25, h - hw)
    h -= hw
    h -= 15
    c.setFont("Helvetica-Bold", 12)
    h -= 22
    c.drawString(25, h, _(u"Account holder"))
    h -= 22
    c.drawString(25, h, _(u"Address"))
    h -= 22
    c.drawString(25, h, _(u"Postal code"))
    h -= 22
    c.drawString(25, h, _(u"City"))
    h -= 22
    c.drawString(25, h, _(u"Country"))
    h -= 22
    if isinstance(authorization, Authorization):
        if authorization.person.is_employee():
            c.drawString(25, h, _(u"Employee number"))
        else:
            c.drawString(25, h, _(u"Student number"))
    elif isinstance(authorization, tuple):
        # authorization is a tuple of (Authorization, UnverifiedEnrollment), always a student
        c.drawString(25, h, _(u"Student number"))
    h -= 22
    c.drawString(25, h, _(u"IBAN"))
    h -= 22
    c.drawString(25, h, _(u"BIC"))

    h += 22 * 7
    c.setFont("Helvetica", 12)

    if isinstance(authorization, Authorization):
        c.drawString(160, h, authorization.account_holder_name)
        h -= 22
        c.drawString(160, h, authorization.person.address)
        h -= 22
        c.drawString(160, h, authorization.person.postal_code)
        h -= 22
        c.drawString(160, h, authorization.person.city)
        h -= 22
        c.drawString(160, h, authorization.person.country)
        h -= 22
        try:
            c.drawString(160, h, u"%s" % authorization.person.student.student_number())
        except Person.student.RelatedObjectDoesNotExist:
            # no student details
            try:
                c.drawString(160, h, "%s" % authorization.person.employee.employee_number())
            except Person.employee.RelatedObjectDoesNotExist:
                pass  # No employee details
        h -= 22
        c.drawString(160, h, authorization.iban)
        h -= 22
        if authorization.bic:
            c.drawString(160, h, authorization.bic)
    elif isinstance(authorization, tuple):
        # authorization is a tuple of (Authorization, UnverifiedEnrollment)
        c.drawString(160, h, authorization[0].account_holder_name)
        h -= 22
        c.drawString(160, h, authorization[1].address)
        h -= 22
        c.drawString(160, h, authorization[1].postal_code)
        h -= 22
        c.drawString(160, h, authorization[1].city)
        h -= 22
        c.drawString(160, h, authorization[1].country)
        h -= 22
        if authorization[1].student_number is not None:
            c.drawString(160, h, u"%s" % authorization[1].student_number)
        else:
            pass  # no student details
        h -= 22
        c.drawString(160, h, authorization[0].iban)
        h -= 22
        if authorization[0].bic:
            c.drawString(160, h, authorization[0].bic)

    # signature box, always at static position for digital signature.
    c.setFont("Helvetica", 12)
    c.drawString(25, 170, _("By signing this form, undersigned agrees with the arrangement as described above."))
    if signing_date is not None:
        c.drawString(25, 145, _("Signature on %(date)s:") % {'date': signing_date.strftime('%d-%m-%Y')})
    else:
        c.drawString(25, 145, _("Signature:"))

    p = c.beginPath()
    p.moveTo(25, 135)
    p.lineTo(275, 135)
    p.lineTo(275, 25)
    p.lineTo(25, 25)
    p.lineTo(25, 135)
    c.setDash([], 0)
    c.drawPath(p)


    c.showPage()


def pdf_declaration_form(file, declaration):
    with translation.override(declaration.person.preferred_language):
        c = canvas.Canvas(file, pagesize=A4)
        pdf_declaration_page(c, declaration)
        c.save()


def pdf_declaration_page(c, declaration):
    """
    Generates a PDF page for the given declaration.
    """

    c.setTitle(_("Expense claim"))

    width, height = A4

    c.setFont("Helvetica-Bold", 34)
    c.drawString(25, height - 60, _("Expense claim"))

    # Inter-Actief logo
    # Original: 1198*226
    c.drawInlineImage(Image.open('%s/amelie/style/static/img/pdf/inter-actief.png' % settings.BASE_PATH),
                      x=width - 25 - 240,
                      y=height - 25 - 45,
                      width=240,
                      height=45)

    h = height - 80

    c.setFont("Helvetica", 12)
    text = _("This expense claim form has been automatically generated by Amélie.")
    style = getSampleStyleSheet()['BodyText']
    style.fontSize = 12
    style.leading = 17
    p = Paragraph(text, style)
    ww, hw = p.wrap(width - 50, 100)
    p.drawOn(c, 25, h - hw - 3)
    h -= hw
    h -= 10

    h -= 15
    c.drawString(25, h, _("The following expense claim was submitted via the website."))
    h -= 30

    p = c.beginPath()
    c.setLineWidth(1)
    p.moveTo(25, h)
    p.lineTo(570, h)
    c.drawPath(p)
    h -= 40


    c.setFont("Helvetica-Bold", 20)
    c.drawString(25, h, _("Details of the claimant:"))
    h -= 10

    reset_height = h

    c.setFont("Helvetica-Bold", 12)
    h -= 25
    c.drawString(25, h, _("Name"))
    h -= 25
    c.drawString(25, h, _("Committee"))
    h -= 25
    c.drawString(25, h, _("IBAN"))
    h -= 25


    p = c.beginPath()
    c.setLineWidth(1)
    p.moveTo(25, h)
    p.lineTo(570, h)
    c.drawPath(p)
    h -= 40


    c.setFont("Helvetica-Bold", 20)
    c.drawString(25, h, _("Details of the declaration:"))
    h -= 10

    c.setFont("Helvetica-Bold", 12)
    h -= 25
    c.drawString(25, h, _("Payment Method"))
    h -= 25
    c.drawString(25, h, _("Amount"))
    h -= 25
    c.drawString(25, h, _("Submission date"))
    h -= 25
    c.drawString(25, h, _("Attachments"))

    # Depends on the number of document (names), different height is added
    if (declaration.get_document_names()):
        for doc_name in declaration.get_document_names():
            h -= 12
        h -= 12
    else:
        h -= 25

    c.drawString(25, h, _("Description"))
    
    # Reset height
    h = reset_height

    # data
    c.setFont("Helvetica", 12)

    data_left = 240

    h -= 25
    c.drawString(data_left, h, declaration.person.full_name())
    h -= 25
    c.drawString(data_left, h, declaration.get_committee())
    h -= 25
    c.drawString(data_left, h, declaration.get_iban())
    h -= 25


    h -= 50
    
    h -= 25
    c.drawString(data_left, h, declaration.get_payment_method())
    h -= 25
    c.drawString(data_left, h, '€ %s' % (declaration.amount))
    h -= 25
    c.drawString(data_left, h, declaration.submission_date.strftime('%d-%m-%Y'))
    

    # Adding document names in smaller text in a for loop
    if (declaration.get_document_names()):
        h -= 13
        c.setFont("Helvetica", 10)
        for doc_name in declaration.get_document_names():
            h -= 12
            c.drawString(data_left, h, doc_name)
    else:
        h -= 25
        c.drawString(data_left, h, "No documents attached")

    h -= 15


    # Adding the description that wraps
    d_style = getSampleStyleSheet()['BodyText']
    d_style.fontName = 'Helvetica'
    d_style.fontSize = 12
    d_style.leading = 14
    d_style.wordWrap = 'LTR'
    d_p = Paragraph(force_str(declaration.description), d_style)
    w_available = width - data_left - 25
    d_width, d_height = d_p.wrap(w_available, h)
    d_p.drawOn(c, data_left, h - d_height + 2)

    c.showPage()
