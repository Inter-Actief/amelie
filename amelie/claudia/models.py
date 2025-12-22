import logging
from typing import Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.core.validators import EmailValidator
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.utils.translation import gettext_lazy as _l

from amelie.claudia.mappable import Mappable
from amelie.claudia.tools import strip_domains, unify_mail, verify_instance, \
    verify_instance_attr, verify_extra_alias
from amelie.members.models import Person, Committee, DogroupGeneration
from amelie.tools.encodings import normalize_to_ascii

logger = logging.getLogger(__name__)

CLAUDIA_PERSON_POSTFIX = 'Person'
CLAUDIA_GROUP_POSTFIX = 'Group'


class ExtraGroup(models.Model, Mappable):
    """Manually created group"""

    name = models.CharField(max_length=100)
    active = models.BooleanField(default=False)
    email = models.EmailField(blank=True)
    adname = models.CharField(max_length=50, blank=True)
    dogroup = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    gitlab = models.BooleanField(default=False, verbose_name=_l('Create GitLab group'),
                                 help_text=_l('Members of this group get access to GitLab'))

    def clean(self):
        super(ExtraGroup, self).clean()
        if self.email and not any(self.email.endswith(domain) for domain in settings.IA_MAIL_DOMAIN):
            raise ValidationError({'email': _l(
                'If an email address for an extra group is set, then it may only point to an Inter-Actief server.'
            )})

        # Check if the email address is already in use!
        if self.email and Mapping.objects.filter(email=self.email).exists():

            # Already in use, if it's us, then it's fine
            if len(Mapping.objects.filter(email=self.email)) > 1 or \
                Mapping.objects.get(email=self.email).get_mapped_object() != self:
                raise ValidationError({'email': _l(
                    'This email address is already in use by another mapping!'
                )})

    def is_active(self):
        """Is the group active?"""
        return self.active

    def get_name(self):
        """Get the full name of the group"""
        return self.name

    def get_adname(self):
        """Get the wanted Active Directory name of the group"""
        return self.adname

    def get_email(self):
        """Get the e-mail address of the group"""
        return self.email

    def is_dogroup(self):
        """Is this group a Do-group?"""
        return self.dogroup

    def get_absolute_url(self):
        return reverse('claudia:extragroup_view', args=(), kwargs={'pk': self.id})

    def get_extra_data(self):
        """Get extra data of this group"""
        return {
            'gitlab': self.gitlab,
        }

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-active', 'name']


class SharedDrive(models.Model, Mappable):
    """Shared Drive on GSuite"""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def get_name(self):
        return self.name

    def is_shareddrive(self):
        """Is a shared drive?"""
        return True

    def is_active(self):
        """Is active member or group?"""
        return False

    def is_needed(self):
        """Shared Drives are always needed and in use"""
        return True

    def get_absolute_url(self):
        return reverse('claudia:shareddrive_view', args=(), kwargs={'pk': self.id})

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name', ]


class ExtraPerson(models.Model, Mappable):
    """Manually created person"""

    name = models.CharField(max_length=100)
    active = models.BooleanField(default=False)
    email = models.EmailField(blank=True)
    adname = models.CharField(max_length=50)
    description = models.TextField(blank=True)

    def is_active(self):
        """Is this member an active member?"""
        return self.active

    def get_name(self):
        """Get the full name of this person"""
        return self.name

    def get_adname(self):
        """Get the Active Directory name of this person"""
        return self.adname

    def get_email(self):
        """Get the e-mail address of this person"""
        return self.email

    def get_absolute_url(self):
        return reverse('claudia:extraperson_view', args=(), kwargs={'pk': self.id, })

    def clean(self):
        super(ExtraPerson, self).clean()
        if self.email and not any(self.email.endswith(domain) for domain in settings.IA_MAIL_DOMAIN):
            raise ValidationError({'email': _l(
                'If an extra person has an email than the email address may only point to an Inter-Actief server.'
            )})

        # Check if the email address is already in use!
        if self.email and Mapping.objects.filter(email=self.email).exists():

            # Already in use, if it's us, then it's fine
            if len(Mapping.objects.filter(email=self.email)) > 1 or \
                Mapping.objects.get(email=self.email).get_mapped_object() != self:
                raise ValidationError({'email': _l(
                    'This email address is already in use by another mapping!'
                )})

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-active', 'name']


class AliasGroup(models.Model, Mappable):
    """Group of mappings (and optionally e-mail addresses) that is reachable via one e-mail address"""
    name = models.CharField(max_length=100)
    active = models.BooleanField(default=False)
    email = models.EmailField(unique=True, blank=True)
    description = models.TextField(blank=True)
    open_to_signup = models.BooleanField(default=False, verbose_name=_l("Open to sign up for members"), help_text=_l("Note: Description becomes public"))

    def is_active(self):
        """Is this member an active member?"""
        return self.active

    def get_name(self):
        """Get the full name of this person"""
        return self.name

    def get_email(self):
        """Get the e-mail address of this person"""
        return self.email

    def get_absolute_url(self):
        return reverse('claudia:aliasgroup_view', args=(), kwargs={'pk': self.id, })

    def clean(self):
        super(AliasGroup, self).clean()
        if not any(self.email.endswith(domain) for domain in settings.IA_MAIL_DOMAIN):
            raise ValidationError({'email': _l(
                'An alias group may only point to an Inter-Actief server.'
            )})

        # Check if the email address is already in use!
        if self.email and Mapping.objects.filter(email=self.email).exists():

            # Already in use, if it's us, then it's fine
            if len(Mapping.objects.filter(email=self.email)) > 1 or \
                Mapping.objects.get(email=self.email).get_mapped_object() != self:
                raise ValidationError({'email': _l(
                    'This email address is already in use by another mapping!'
                )})

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-active', 'name']


class Contact(models.Model, Mappable):
    """Contact details of an external address that needs to be included in some of our groups for some reason."""
    name = models.CharField(max_length=100)
    active = models.BooleanField(default=False)
    email = models.EmailField(blank=True, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def clean(self):
        if self.email and any(self.email.endswith(domain) for domain in settings.IA_MAIL_DOMAIN):
            raise ValidationError({'email': _l('A contact address is not to point to an Inter-Actief server.')})

        # Check if the email address is already in use!
        if self.email and Mapping.objects.filter(email=self.email).exists():

            # Already in use, if it's us, then it's fine
            if len(Mapping.objects.filter(email=self.email)) > 1 or Mapping.objects.get(
                email=self.email).get_mapped_object() != self:
                raise ValidationError({'email': _l(
                    'This email address is already in use by another mapping!'
                )})

    def is_active(self):
        return self.active

    def get_name(self):
        return self.name

    def get_email(self):
        return self.email

    def get_absolute_url(self):
        return reverse('claudia:contact_view', args=(), kwargs={'pk': self.id, })

    def get_extra_data(self):
        return {'description': self.description}


class Mapping(models.Model):
    """Mapping between Claudia and the original objects"""

    RELATED_CLASSES = {
        'AmeliePerson': Person,
        'AmelieGroup': Committee,
        'AmelieDoGroup': DogroupGeneration,
        'ExtraGroup': ExtraGroup,
        'ExtraPerson': ExtraPerson,
        'AliasGroup': AliasGroup,
        'Contact': Contact,
        'SharedDrive': SharedDrive,
    }

    type = models.CharField(max_length=25)
    ident = models.IntegerField()
    # Name max_length must be >= the max_length of the name of any mapping type
    # (Person has 50 first_name + 1 space + 25 infix + 1 space + 50 last_name = 127. 150 is a nice margin.)
    name = models.CharField(max_length=150, blank=True)
    active = models.BooleanField(default=False)
    email = models.EmailField(blank=True)
    adname = models.CharField(max_length=50, blank=True)
    guid = models.CharField(max_length=24, blank=True)
    kanidm_id = models.CharField(max_length=100, blank=True, null=True)
    gsuite_id = models.CharField(max_length=100, blank=True, null=True)
    gsuite_forwarding_enabled = models.BooleanField(default=False)

    @staticmethod
    def get_type(obj):
        """Get type-string for given object"""
        cls = obj.__class__
        for t in Mapping.RELATED_CLASSES:
            if cls == Mapping.RELATED_CLASSES[t]:
                return t

    @staticmethod
    def get_object_from_mapping(obj_type, ident):
        """Get object from type and ident"""
        return Mapping.RELATED_CLASSES[obj_type].from_id(ident)

    @classmethod
    def create(cls, obj):
        """Create mapping for object"""
        mp = cls(name=normalize_to_ascii(obj.get_name()), type=Mapping.get_type(obj), ident=obj.id)
        mp.save()
        return mp

    @classmethod
    def find(cls, obj):
        """Find mapping for object"""
        try:
            return Mapping.objects.get(type=Mapping.get_type(obj), ident=obj.id)
        except Mapping.DoesNotExist:
            return None

    @classmethod
    def wrap(cls, obj):
        """Find or create mapping for object"""
        mp, created = Mapping.objects.get_or_create(type=Mapping.get_type(obj),
                                                    ident=obj.id, defaults={'name': normalize_to_ascii(obj.get_name())})
        return mp

    def _obj(self):
        """
        Get the mapped object.

        Store the result to prevent multiple queries.

        :rtype: Mappable
        """
        if not hasattr(self, '_object'):
            self._object = Mapping.get_object_from_mapping(self.type, self.ident)

        return self._object

    def get_mapped_object(self):
        """Get the mapped object."""
        return self._obj()

    def get_guid(self):
        """Get binary GUID"""
        if self.guid:
            import base64

            return base64.b64decode(self.guid)

    def set_guid(self, guid):
        """Set binary GUID"""
        import base64

        if guid:
            guid_b = base64.b64encode(guid).decode("utf-8")
        else:
            guid_b = ''
        self.guid = guid_b

    def get_kanidm_id(self) -> Optional[str]:
        """Get Kanidm ID"""
        if self.kanidm_id:
            return self.kanidm_id
        return None

    def set_kanidm_id(self, kanidm_id: Optional[str]):
        """Set Kanidm ID"""
        self.kanidm_id = kanidm_id
        self.save()

    def get_gsuite_id(self):
        if self.gsuite_id:
            return self.gsuite_id

    def set_gsuite_id(self, gsuite_id):
        """Set G-Suite ID"""
        self.gsuite_id = gsuite_id
        self.save()

    def check_mapping(self, fix=False):
        """Check if the name and e-mail address of this mapping are still correct, and change them if necessary."""
        logger.debug("Checking basics of %s (cid: %s)" % (self.name, self.id))

        if not fix:
            logger.debug("No changes will me made to internal attributes")

        obj = self._obj()
        changes = []

        # Check name
        name = normalize_to_ascii(obj.get_name())
        if name != self.name:
            logger.debug("Name changed to %s (was: %s)" % (name, self.name))
            changes.append(("name", (self.name, name)))
            if fix:
                self.name = name
                self.save()

        # Check e-mail
        email = unify_mail(obj.get_email()) or ''
        if email != self.email:
            logger.debug("Mail changed to %s (was: %s)" % (email, self.email))
            changes.append(("mail", (self.email, email)))
            if fix:
                self.email = email
                self.save()

        # Check AD-name
        adname = normalize_to_ascii(obj.get_adname()) or ''
        if adname != self.adname:
            logger.debug("ADName changed to %s (was: %s)" % (adname, self.adname))
            changes.append(("adname", (self.adname, adname)))
            if fix:
                self.adname = adname
                self.save()

        return changes

    def is_person(self):
        return self.type.endswith(CLAUDIA_PERSON_POSTFIX)

    def is_group(self):
        return self.type.endswith(CLAUDIA_GROUP_POSTFIX)

    def is_contact(self):
        return self.type == "Contact"

    def is_committee(self):
        return self._obj().is_committee()

    def is_dogroup(self):
        return self._obj().is_dogroup()

    def is_shareddrive(self):
        return self._obj().is_shareddrive()

    def givenname(self):
        """Get the first name if this is a person"""
        if self.is_person():
            return normalize_to_ascii(self._obj().get_givenname())

    def surname(self):
        """Gets the last name if this is a person"""
        if self.is_person():
            return normalize_to_ascii(self._obj().get_surname())

    def get_drivename(self):
        if self.is_shareddrive():
            return self.name

    def extra_data(self):
        """Gets a dictionary with extra data of this mapping"""
        return self._obj().get_extra_data()

    def is_needed(self):
        """Is this mapping still used for anything?"""
        return (self._obj().is_needed()
                or self.extra_members.exists()
                or self.extra_groupmemberships.exists())

    def needs_account(self):
        """Gets if this user/group needs an AD-account"""
        return self._obj().is_active() or len(
            [group for group in self.extra_groups('ad') if not group.is_dogroup()]) > 0

    def needs_gsuite_account(self):
        """Gets if this user/group needs a GSuite account"""
        required_check = bool(self.adname) if self.is_person() else bool(self.email)
        return (self._obj().is_active() and required_check) or self.is_shareddrive()

    def is_group_active(self):
        """Is this group active?"""
        return self.needs_account()

    def is_gsuite_group_active(self):
        """Is this group active?"""
        return self.needs_gsuite_account()

    def extra_groups(self, select):
        """
        Give a list of groups that this mapping has been manually added to.
        :param select: Choice from: ['all', 'mail', 'ad', 'shared_drive']
            'all' = All extra groups
            'mail' = Extra groups for e-mail
            'ad' = Extra groups for AD
            'shared_drive' = Shared Drive
        """

        if select == 'all':
            memberships = self.extra_groupmemberships.all()
        elif select == 'mail':
            memberships = self.extra_groupmemberships.filter(mail=True)
        elif select == 'ad':
            memberships = self.extra_groupmemberships.filter(ad=True)
        elif select == 'shared_drive':
            memberships = self.extra_groupmemberships.filter(shared_drive=True)
        else:
            raise ValueError('Invalid select choice')

        return [membership.group for membership in memberships]

    def groups(self, select):
        """
        Give a list of groups that this mapping is in. This includes the extra groups and aliases.
        :param select: Choice from: ['all', 'mail', 'ad', 'shared_drive']
            'all' = All extra groups
            'mail' = Extra groups for e-mail
            'ad' = Extra groups for AD
            'shared_drive' = Shared drive
        """
        obj = self._obj()

        # Groups according to own database
        groups = [self.wrap(group) for group in obj.groups()]

        # Extra groups
        groups.extend(self.extra_groups(select=select))

        # Add "Actievelingen" and "Webmasters" to person if needed
        if self.is_person() and self.needs_account() and select in ['ad', 'all']:
            groups.append(Mapping.objects.get(id=settings.CLAUDIA_MAPPING_ACTIVE_MEMBERS))  # Actievelingen

            if obj.is_webmaster():
                groups.append(Mapping.objects.get(id=settings.CLAUDIA_MAPPING_WEBMASTERS))  # Webmasters

        return set(groups)

    def all_groups(self, select):
        """
        Give a list of all groups that this mapping is in, including upper groups. This includes the extra groups.
        :param select: Choice from: ['all', 'mail', 'ad']
            'all' = All extra groups
            'mail' = Extra groups for e-mail
            'ad' = Extra groups for AD
        """
        result = set(self.groups(select))
        visited = set()

        to_visit = result - visited
        while to_visit:
            group = to_visit.pop()

            result |= set(group.groups(select))
            visited.add(group)

            to_visit = result - visited

        return list(result)

    def members(self, old_members=False):
        """
        Gives a list of all mappings that are a member of this group, or all old members if specified.
        """
        # Members according to own database
        if not self.is_group() and not self.is_shareddrive():
            return []

        members = []

        # Loop over objects in the objects' members list
        for obj in self._obj().members(old_members):
            # If we are checking old members we should only search and not create mappings
            if old_members:
                new_member = self.find(obj)
            else:
                new_member = self.wrap(obj)

            # self.find can return None, so don't add it if it is None
            if new_member is not None:
                members.append(new_member)

        # After all normal members have been checked, add the extra members / manual members
        members.extend([membership.member for membership in self.extra_members.all()])

        return members

    def personal_aliases(self):
        """Gets the personal aliases this mapping needs to be in"""
        if self.is_person():
            aliases = self._obj().personal_aliases()
            if self.adname and self.needs_gsuite_account():
                aliases.append(self.adname)
            return aliases
        else:
            return []

    def aliases(self):
        """Give a list of all aliases this mapping is in"""
        # First the groups
        aliases = [group.email for group in self.groups(select='mail') if group.email]
        # Personal Aliases
        aliases += self.personal_aliases()

        aliases = [strip_domains(alias) for alias in aliases]  # strip domains from internal aliases
        aliases = [alias for alias in aliases if '@' not in alias]  # Filter all external addresses from the list

        return aliases

    def get_absolute_url(self):
        return reverse('claudia:mapping_view', args=(), kwargs={'pk': self.id, })

    def __str__(self):
        return self.name or '#%d' % self.id

    class Meta:
        ordering = ['name', 'id']
        unique_together = [['type', 'ident']]


class Membership(models.Model):
    """Manual addition of a mapping (person or group) to a group"""

    group = models.ForeignKey(Mapping, related_name='extra_members', on_delete=models.CASCADE)
    member = models.ForeignKey(Mapping, related_name='extra_groupmemberships', on_delete=models.CASCADE)
    ad = models.BooleanField(default=False)
    mail = models.BooleanField(default=False)
    shared_drive = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    def __str__(self):
        return '%s in %s' % (self.member, self.group)

    class Meta:
        ordering = ['group', 'member']
        unique_together = [['group', 'member']]


post_save.connect(verify_instance_attr, Membership)
post_delete.connect(verify_instance_attr, Membership)


class ExtraPersonalAliasEmailValidator(EmailValidator):
    message = _l("E-mail address domain part must be one of {}".format(settings.CLAUDIA_GSUITE['ALLOWED_ALIAS_DOMAINS']))
    domain_allowlist = settings.CLAUDIA_GSUITE['ALLOWED_ALIAS_DOMAINS']

    def validate_domain_part(self, domain_part):
        return domain_part in self.domain_allowlist


class ExtraPersonalAlias(models.Model):
    """
    An extra personal alias that can be added to a Mapping.
    This needs to be unique in the entire system, but it only checks for uniqueness with other extra personal aliases.
    """
    email = models.EmailField(
        validators=[ExtraPersonalAliasEmailValidator()],
        unique=True
    )
    mapping = models.ForeignKey(to=Mapping, related_name="extra_personal_aliases", on_delete=models.CASCADE)

    def __str__(self):
        return self.email


class Event(models.Model):
    """A planned event"""

    type = models.CharField(max_length=25)
    mapping = models.ForeignKey(Mapping, on_delete=models.CASCADE)
    execute = models.DateTimeField()

    def __str__(self):
        return '%s %s on %s' % (self.type, self.mapping, self.execute)

    class Meta:
        ordering = ['-execute', ]


class Timeline(models.Model):
    """Timeline entry"""

    datetime = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100, blank=True)
    mapping = models.ForeignKey(Mapping, blank=True, null=True, on_delete=models.SET_NULL)
    type = models.CharField(max_length=25, blank=True)
    description = models.TextField()

    @classmethod
    def create(cls, name, mp, obj_type, descr=''):
        """ Create Timeline entry """
        cls(name=name, mapping=mp, type=obj_type, description=descr).save()

    def __str__(self):
        return '%s %s: %s' % (self.type, self.name, self.description)

    class Meta:
        ordering = ['-datetime', '-id']


class DrivePermission(models.Model):
    """Link to get drive permission from mappable object and drive"""
    drive = models.ForeignKey(SharedDrive, on_delete=models.CASCADE)
    mapping = models.ForeignKey(Mapping, on_delete=models.CASCADE)
    permission_id = models.CharField(max_length=512)

    class Meta:
        ordering = ['drive', 'mapping']

    def __str__(self):
        return f"Permission for {self.mapping} in {self.drive}"


post_save.connect(verify_instance, ExtraPerson)
post_save.connect(verify_instance, ExtraGroup)
post_save.connect(verify_instance, AliasGroup)
post_save.connect(verify_instance, Contact)
post_save.connect(verify_instance, SharedDrive)
post_save.connect(verify_extra_alias, ExtraPersonalAlias)
post_delete.connect(verify_extra_alias, ExtraPersonalAlias)
