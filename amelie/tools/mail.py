from amelie.iamailer import Recipient


def person_dict(person):
    """
    Create a dict with selected information about a person.

    Only includes information members are allowed to include in an email.
    """
    pdata = {
        'first_name': person.first_name,
        'last_name': person.last_name,
        'incomplete_name': person.incomplete_name(),
        'address': person.address,
        'postal_code': person.postal_code,
        'city': person.city,
        'country': person.country,
        'student': None,
    }

    # Get student number in different ways depending on if it's a Person or UnverifiedEnrollment.
    if hasattr(person, 'student_number'):
        pdata['student'] = {'number': person.student_number}

    if hasattr(person, 'student'):
        pdata['student'] = {'number': person.student.number}

    return pdata


class PersonRecipient(Recipient):
    def __init__(self, recipient, context=None, headers=None, ccs=None, bccs=None, attachments=None):
        """
        Recipient based on a Person object.
        :param recipient: Person to which the mail needs to be sent.
        :type recipient: amelie.leden.models.Person
        :param context: Dict with context data. 'recipient' is automatically added to the context.
        :param headers: Dict with header data.
        :param ccs: List of CC addresses.
        :param bccs: List of BCC addresses.
        :return:
        """

        tos = ['"{}" <{}>'.format(recipient.incomplete_name(), recipient.email_address)]
        language = recipient.preferred_language

        if not context:
            context = {}
        context['recipient'] = person_dict(recipient)

        super(PersonRecipient, self).__init__(tos, context, headers, ccs, bccs, language, attachments)
