"""Contains the "Mappable" abstract class"""


class Mappable:
    """
    Base object that can be used in a Mapping.
    Designed to be used with another class that is extending models.Model

    Methods can be overridden to implement functionality specific to a single kind of mapping.
    """

    @classmethod
    def from_id(cls, ident):
        """
        Give an object based on its unique id
        :param ident: Object id
        """
        return cls.objects.get(id=ident)

    @classmethod
    def get_all(cls):
        """
        Give all existing objects
        """
        return cls.objects.all()

    # ============ General queries ============

    def is_needed(self):
        """
        Does this object need a mapping?
        """
        return self.is_active() or self.groups() or self.members()

    def is_active(self):
        """
        Is this object active?
        """
        return False

    def get_name(self):
        """
        Give the name of this object
        """
        return ''

    def get_adname(self):
        """
        Give the Active Directory name of this object
        """
        return ''

    def get_email(self):
        """
        Give the e-mail address of this object
        """
        return ''

    def groups(self):
        """
        Give the groups of this object
        """
        return []

    def get_absolute_url(self):
        """
        Give the canonical URL of this object
        """
        return None

    def get_extra_data(self):
        """
        Give a dictionary of extra data for this object
        """
        return dict()

    def __str__(self):
        return self.get_name()

    # ============ Person-only query's ============

    def is_webmaster(self):
        """
        Is this person a webmaster?
        """
        return False

    def get_givenname(self):
        """
        Give the first name of this person
        """
        return ''

    def get_surname(self):
        """
        Give the last name of this person
        """
        return ''

    def personal_aliases(self):
        """
        Give the personal aliases (without domain name) of this person
        """
        return []

    # ============ Group-only query's ============

    def is_committee(self):
        """
        Is this group a committee
        """
        return False

    def is_dogroup(self):
        """
        Is this group a do-group?
        """
        return False

    def members(self, old_members=False):
        """
        Give the members of this group
        :param bool old_members: Also give the old-members that once were in this group.
        """
        return []

    def is_shareddrive(self):
        """
        Is this a shared drive?
        """
        return False
