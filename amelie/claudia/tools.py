import re

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.forms import ModelMultipleChoiceField

from amelie.claudia import tasks

MAIL_DOMAINS = ['inter-actief.net', 'inter-actief.utwente.nl']

MAIL_ALIAS_REGEX = re.compile(r'^[a-zA-Z0-9_.-]+$')


def unify_mail(email, primary_domain=None):
    """Converts everything into a neat e-mail address"""
    if email is None:
        return ''
    email = email.strip()
    if email == '':
        return ''
    if '@' not in email:
        user = email
        domain = None
    else:
        (user, domain) = email.split('@')

    if not domain or domain in MAIL_DOMAINS:
        domain = primary_domain if primary_domain else MAIL_DOMAINS[0]
    return '%s@%s' % (user, domain)


def strip_domains(email):
    """Extract the domain from the email if it contains one of the MAIL_DOMAINS."""
    if '@' in email:
        for domain in MAIL_DOMAINS:
            if email.lower().endswith(domain):
                email = email[:email.find('@')]
    return email


def is_alias(email):
    """ Is this email a valid alias?"""
    return MAIL_ALIAS_REGEX.match(strip_domains(email))


def is_valid_email(email):
    try:
        validate_email(email)

        return True
    except ValidationError:
        return False


def guid2hexstring(val):
    s = ['\\%02X' % x for x in val]
    return ''.join(s)


def encode_guid(guid):
    """Converts a binary string into its escaped hexadecimal notation."""
    # Convert GUID to normal string
    res = guid2hexstring(guid).replace("\\", "")  # '496772AF62194D45B2503963FBA0E277'
    # and convert guid to a value you can use in an ldap search filter
    res = ''.join(['\\%s' % res[i:i + 2] for i in
                  range(0, len(res), 2)])  # '\\49\\67\\72\\AF\\62\\19\\4D\\45\\B2\\50\\39\\63\\FB\\A0\\E2\\77'
    return res


def create_password(length=32):
    """
    Create a long, random password
    """
    import random
    import string
    # Generate random characters
    alphabet = string.digits + string.ascii_letters + string.punctuation
    passwd = []
    for i in range(length):
        passwd.append(random.choice(alphabet))
    passwd = ''.join(passwd)
    return passwd


def is_verifiable(obj):
    """
    Is it possible to verify this object?
    """
    from amelie.claudia.models import Mapping

    if isinstance(obj, Mapping):
        return True

    for k in Mapping.RELATED_CLASSES:
        if isinstance(obj, Mapping.RELATED_CLASSES[k]):
            return True

    return False


def verify_instance(**kwargs):
    """
    Verify object in instance-argument.

    Used in post_save signals.
    """
    instance = kwargs.get('instance')

    from amelie.claudia.models import Mapping

    transaction.on_commit(lambda: tasks.verify_instance.delay(Mapping.get_type(instance), instance.id))


def verify_extra_alias(**kwargs):
    instance = kwargs.get('instance')
    transaction.on_commit(lambda: tasks.verify_mapping.delay(instance.mapping.id))


def verify_instance_attr(sender, **kwargs):
    from amelie.claudia.models import Mapping, Membership

    if sender == Membership:
        attr_name = 'member'
    else:
        raise ValueError

    instance = kwargs.get('instance')
    try:
        obj = getattr(instance, attr_name)
        """:type : Mappable"""
    except ObjectDoesNotExist:
        # Object was apparently removed sometime.
        return

    if isinstance(obj, Mapping):
        transaction.on_commit(lambda: tasks.verify_mapping.delay(obj.id))
    else:
        transaction.on_commit(lambda: tasks.verify_instance.delay(Mapping.get_type(obj), obj.id))


def format_changes(changes):
    info = []
    for (cat, data) in changes:
        if data.__class__.__name__ == 'list':
            info.append('%s: %s' % (cat, ' '.join(data)))
        elif data.__class__.__name__ == 'tuple' and len(data) == 2:
            (old, new) = data
            info.append('%s: %s -> %s' % (cat, old, new))
        else:
            info.append('%s: %s' % (cat, data))
    return ', '.join(info)


class MailAliasModelMultipleChoiceField(ModelMultipleChoiceField):

    def label_from_instance(self, obj):
        return f"{obj.get_email()} - {obj.description}"
