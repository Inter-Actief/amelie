import datetime
import logging

import ldap
import ldap.dn
from django.utils.timezone import utc

from amelie.claudia.tools import encode_guid

logger = logging.getLogger(__name__)


#
# ad.py
# Interface to the Inter-Actief Active Directory
# b.c.peschier, m.kooijman & k.alberts

# These constants are taken from from samba code in include/ads.h
UF_NORMAL_ACCOUNT = 0x200
UF_ACCOUNTDISABLE = 0x002


class AD(object):
    def __init__(self, proto, host, username, password, base_dn, port, ca_cert_path):
        """Initialize connection with all options you can think of"""
        self.conn_string = proto + "://" + host + ":" + str(port) + "/"
        self.realm = '.'.join([v for [(k, v, x)] in ldap.dn.str2dn(base_dn) if k == 'dc'])
        if '@' not in username and ',' not in username:
            username = '%s@%s' % (username, self.realm)
        self.username = username
        self.password = password  # XXX solve reconnect differently?
        self.baseDN = base_dn
        self.ca_cert_path = ca_cert_path
        # Use any dc components from the base_dn to build the realm
        self.ldap = None
        self.connect()

    # =============== Connection functions ===============

    #
    # Solve problems with loss of connection
    #
    def connect(self):
        """Try to connect to the AD server"""
        try:

            self.ldap = ldap.initialize(self.conn_string, bytes_mode=False)
            # Set LDAP protocol version used
            self.ldap.protocol_version = ldap.VERSION3
            # Force cert validation
            self.ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_DEMAND)
            # Set path name of file containing all trusted CA certificates
            self.ldap.set_option(ldap.OPT_X_TLS_CACERTFILE, self.ca_cert_path)
            # Force libldap to create a new SSL context (must be last TLS option!)
            self.ldap.set_option(ldap.OPT_X_TLS_NEWCTX, 0)
            # Logon to the AD
            self.ldap.simple_bind_s(str(self.username), str(self.password))

            logger.debug('Connected to Active Directory')
        except ldap.LDAPError as e:
            logger.error('Could not connect to Active Directory. {}'.format(e))
            raise e

    # ================= Search functions =====================

    #
    # Search by DN
    #

    def get_object(self, dn):
        """
        Create an ADAccount or ADGroup by using a DN
        """
        attrs = self.get_attributes(dn)
        if b'group' in attrs['objectClass']:
            return ADGroup(self, dn)
        elif b'user' in attrs['objectClass']:
            return ADAccount(self, dn)
        else:
            return None

    #
    # Search by GUID
    #

    def get_guid(self, guid, ou=None):
        """
        Searches the AD for a GUID in an OU. OU is mandatory because of speed concerns.

        Returns a tuple (DN, attributes) or raises ValueError if not found
        """

        search_scope = ldap.SCOPE_SUBTREE
        search_filter = "(objectGUID=%s)" % encode_guid(guid)
        retrieve_attributes = None

        try:
            if ou:
                ldap_result_set = self.ldap.search_s('ou=%s,%s' % (ou, self.baseDN), search_scope, search_filter,
                                                     retrieve_attributes)
            else:
                ldap_result_set = self.ldap.search_s('%s' % self.baseDN, search_scope, search_filter,
                                                     retrieve_attributes)

        except ldap.SERVER_DOWN:
            self.connect()
            return self.get_guid(guid, ou)
        except ldap.LDAPError as e:
            logger.error('Exception: %s' % str(e))
            raise e

        # Return empty tuple if nothing is found
        if len(ldap_result_set) == 0:
            return None, None
        else:
            return ldap_result_set[0]

    def get_person_guid(self, guid):
        """
        Search account by GUID, wraps an ADAccount around getByGUID
        """
        (dn, attrs) = self.get_guid(guid, "Gebruikers")

        if dn is None:
            return None

        if b'person' not in attrs['objectClass']:
            logger.warning('Found object is not an account: %s' % encode_guid(guid))
            return None

        return ADAccount(self, dn, attrs)

    def get_group_guid(self, guid):
        """
        Search group by GUID, wraps an ADGroup around getByGUID
        """
        (dn, attrs) = self.get_guid(guid)

        if dn is None:
            return None

        if b'group' not in attrs['objectClass']:
            logger.warning('Found object is not a group: %s' % encode_guid(guid))
            return None

        return ADGroup(self, dn, attrs)

    #
    # Search by accountname
    #
    def find_person(self, username):
        """
        Search an account with an accountname. Returns an ADAccount
        """

        search_scope = ldap.SCOPE_SUBTREE
        search_filter = str("(sAMAccountName=%s)" % username)
        retrieve_attributes = None
        try:
            ldap_result_set = self.ldap.search_s("ou=Gebruikers,%s" % self.baseDN, search_scope, search_filter,
                                                 retrieve_attributes)
        except ldap.SERVER_DOWN:
            self.connect()
            return self.find_person(username)

        if len(ldap_result_set) == 0:
            return None

        (dn, attrs) = ldap_result_set[0]
        return ADAccount(self, dn, attrs=attrs)

    def find_group(self, group):
        """
        Search a group with an accountname. Returns an ADGroup
        """

        search_scope = ldap.SCOPE_SUBTREE
        search_filter = "(name=%s)" % group
        retrieve_attributes = None
        try:
            ldap_result_set = self.ldap.search_s("%s" % self.baseDN, search_scope, search_filter, retrieve_attributes)
        except ldap.SERVER_DOWN:
            self.connect()
            return self.find_group(group)

        if len(ldap_result_set) == 0:
            return None

        (dn, attrs) = ldap_result_set[0]
        return ADGroup(self, dn, attrs=attrs)

    # ========= List commands =============

    def groups(self, ou):
        """
        Gives a list of all groups in a given OU
        """

        search_scope = ldap.SCOPE_SUBTREE
        search_filter = "(objectClass=group)"
        retrieve_attributes = None
        try:
            ldap_result_set = self.ldap.search_s('%s,%s' % (ou, self.baseDN), search_scope, search_filter,
                                                 retrieve_attributes)
        except ldap.SERVER_DOWN:
            self.connect()
            return self.groups(ou)

        return [ADGroup(self, dn, attrs=attrs) for (dn, attrs) in ldap_result_set]

    # ============= Adding commands =================

    def add_group(self, group_name, commissie=True):
        """
        Adds a group. If it is a committee it is added to the "Commissies", else to "Overig".
        """

        if commissie:
            dn = "cn=%s,ou=Commissies,%s" % (group_name, self.baseDN)
        else:
            dn = "cn=%s,ou=Groepen,%s" % (group_name, self.baseDN)

        mods = [
            ('objectClass', [b'top', b'group']),
            ('cn', group_name.encode()),
            ('name', group_name.encode()),
            ('msSFU30Name', group_name.encode()),
            ('msSFU30NisDomain', 'ia'.encode()),
            ('sAMAccountName', group_name.encode())
        ]

        try:
            self.ldap.add_s(dn, mods)
            return ADGroup(self, dn)

        except ldap.SERVER_DOWN:
            self.connect()
            return self.add_group(group_name, commissie)

    def add_account(self, account_name):
        """
        Adds a user
        """

        upn = str("%s@%s" % (account_name, self.realm))
        dn = str("cn=%s,ou=Gebruikers,%s" % (account_name, self.baseDN))
        uf = str(UF_NORMAL_ACCOUNT | UF_ACCOUNTDISABLE)  # User flags
        homedir = '\\\\ia.utwente.nl\\dfs\\Users\\%s\\home' % account_name
        profilepath = '\\\\ia.utwente.nl\\dfs\\Users\\%s\\profile' % account_name
        unixhomedir = '/data/users/%s/home' % account_name
        mods = [
            ('objectClass', [b'top', b'person', b'organizationalPerson', b'user']),
            ('cn', account_name.encode()),
            ('userPrincipalName', upn.encode()),
            ('name', account_name.encode()),
            ('displayName', account_name.encode()),
            ('sAMAccountName', account_name.encode()),
            ('userAccountControl', uf.encode()),
            ('homeDirectory', homedir.encode()),
            ('homeDrive', 'H:'.encode()),
            ('scriptPath', 'kix32.exe kixtart.kix'.encode()),
            ('profilePath', profilepath.encode()),
            ('msSFU30Name', account_name.encode()),
            ('msSFU30NisDomain', "ia".encode()),
            ('unixHomeDirectory', unixhomedir.encode()),
            ('gidNumber', '20439'.encode()),  # Activelings
            ('loginShell', '/bin/bash'.encode())
        ]
        try:
            self.ldap.add_s(dn, mods)
            return ADAccount(self, dn)

        except ldap.SERVER_DOWN:
            self.connect()
            return self.add_account(account_name)

    # ======= Attribute queries ========

    def get_attributes(self, dn):
        """
        Get the set of attributes of the DN
        """
        search_scope = ldap.SCOPE_SUBTREE
        search_filter = "(objectClass=*)"
        retrieve_attributes = None
        try:
            ldap_result_set = self.ldap.search_s(dn, search_scope, search_filter, retrieve_attributes)
            for (dn, attrs) in ldap_result_set:
                return attrs
        except ldap.SERVER_DOWN:
            self.connect()
            return self.get_attributes(dn)

    def set_single_attribute(self, dn, attr, val):
        """
        Save a single attribute
        """
        # Convert strings to their binary counterparts
        if isinstance(val, str):
            val = val.encode()

        try:
            self.ldap.modify_s(dn, [(ldap.MOD_REPLACE, attr, val)])
        except ldap.SERVER_DOWN:
            self.connect()
            return self.set_single_attribute(dn, attr, val)

    def add_multiple_attributes(self, dn, attr, val):
        """
        Save multiple attributes at the same time
        """
        # Convert strings to their binary counterparts
        if isinstance(val, str):
            val = val.encode()

        # Convert list of strings to list of binary strings
        if isinstance(val, list):
            for i, x in enumerate(val):
                if isinstance(x, str):
                    val[i] = x.encode()

        try:
            self.ldap.modify_s(dn, [(ldap.MOD_ADD, attr, val)])
        except ldap.SERVER_DOWN:
            self.connect()
            return self.add_multiple_attributes(dn, attr, val)

    def delete_multiple_attributes(self, dn, attr, val):
        """
        Remove multiple attributes
        """
        # Convert strings to their binary counterparts
        if isinstance(val, str):
            val = val.encode()

        # Convert list of strings to list of binary strings
        if isinstance(val, list):
            for i, x in enumerate(val):
                if isinstance(x, str):
                    val[i] = x.encode()

        try:
            self.ldap.modify_s(dn, [(ldap.MOD_DELETE, attr, val)])
        except ldap.SERVER_DOWN:
            self.connect()
            return self.delete_multiple_attributes(dn, attr, val)


# ============= AD-object classes ===========

class ADObject(object):
    """
    Base type of the AD objects
    """

    def __init__(self, ad, dn, attrs=None):
        self.ad = ad
        self.dn = dn

        if attrs is None:
            self.attrs = ad.get_attributes(dn)
        else:
            self.attrs = attrs

    # ===== Removing, Moving and Renaming======

    def delete(self):
        """
        Delete this object. WARNING: After this, the account reference is broken.
        """

        try:
            self.ad.ldap.delete_s(self.dn)
        except ldap.SERVER_DOWN:
            self.ad.connect()
            self.delete()

        self.attrs = {}
        self.dn = None

    def move(self, new_adparent, new_name):
        """
        Move this object to a different OU
        """
        newdn = ("OU=%s," % new_name) + ','.join(ldap.explode_dn(new_adparent.dn)[1:])
        try:
            self.ad.ldap.rename_s(self.dn, "CN=%s" % (self.name()), newsuperior=newdn)
        except ldap.SERVER_DOWN:
            self.ad.connect()
            return self.move(new_adparent, new_name)

        # Re-fill our attributes from the AD
        self.dn = newdn
        self.attrs = self.ad.get_attributes(self.dn)

    def rename(self, newname):
        """
        Rename this object
        """
        newcn = "CN=%s" % newname
        try:
            self.ad.ldap.rename_s(self.dn, newcn)
        except ldap.SERVER_DOWN:
            self.ad.connect()
            return self.rename(newname)

        self.dn = str(("%s," % newcn) + ','.join(ldap.explode_dn(self.dn)[1:]))

    # ====== Attribute queries ======

    def single_attribute(self, attr):
        """
        Get a single attribute
        """
        try:
            values = self.attrs[attr]
            assert (len(values) == 1)
            return values[0]
        except KeyError:
            return None

    def set_single_attribute(self, attr, val):
        self.ad.set_single_attribute(self.dn, attr, val)
        self.attrs = self.ad.get_attributes(self.dn)

    def add_multiple_attributes(self, attr, val):
        self.ad.add_multiple_attributes(self.dn, attr, val)
        self.attrs = self.ad.get_attributes(self.dn)

    def delete_multiple_attributes(self, attr, val):
        self.ad.delete_multiple_attributes(self.dn, attr, val)
        self.attrs = self.ad.get_attributes(self.dn)

    # ===== Data queries ====

    def cn(self):
        return self.single_attribute('cn').decode()

    def name(self):
        return self.single_attribute('name').decode()

    def guid(self):
        return self.single_attribute('objectGUID')

    def mail(self):
        mail = self.single_attribute('mail')
        return mail.decode() if mail else None

    def account_name(self):
        return self.single_attribute('sAMAccountName').decode()

    def groups(self, all_groups=False):
        """
        Gives a list of groups that this object is in

        If all_groups is False, only groups that Claudia is allowed to touch are given
        """
        groups = []
        try:
            for group in self.attrs["memberOf"]:
                group = ADGroup(self.ad, group.decode())
                groupdn = ldap.explode_dn(group.dn, notypes=1)[1:]
                if all_groups or "Groepen" in groupdn or "Commissies" in groupdn:
                    groups.append(group)
        except KeyError:  # User is not in any group
            pass
        return groups

    # ==== Data commands ====

    def set_mail(self, mail):
        self.set_single_attribute('mail', mail)

    def set_account_name(self, name):
        self.set_single_attribute('sAMAccountName', name)

    def add_group(self, group):
        """
        Add this object to a group
        """
        group.add_member(self)

    def delete_group(self, group):
        """
        Remove this object from a group
        """
        group.delete_member(self)

    # ==== Update UNIX attributes =====

    def update_uid(self, cid):
        self.set_single_attribute('uidNumber', str(20000 + cid))

    def update_gid(self, cid):
        self.set_single_attribute('gidNumber', str(20000 + cid))

    # ==== Container functions ====

    def container_name(self):
        """
        Give the name of the container this object is in
        """
        return ldap.explode_dn(self.dn, notypes=1)[1]

    def has_container(self, name):
        """
        Does this object have a container (OU)?
        """
        target_dn = "OU=%s,%s" % (name, ','.join(ldap.explode_dn(self.dn)[1:]))
        try:
            attrs = self.ad.get_attributes(target_dn)
            return attrs is not None
        except ldap.NO_SUCH_OBJECT:
            return False

    def delete_container(self, name):
        """
        Remove this object's container
        """
        dn = "OU=%s,%s" % (name, ','.join(ldap.explode_dn(self.dn)[1:]))
        try:
            self.ad.ldap.delete_s(dn)
        except ldap.SERVER_DOWN:
            self.ad.connect()
            self.delete_container(name)

    def create_container(self, name):
        """
        Add a container to this object
        """
        dn = "OU=%s,%s" % (name, ','.join(ldap.explode_dn(self.dn)[1:]))
        mods = [
            ('objectClass', ['top', 'organizationalUnit']),
            ('ou', name),
            ('name', name)
        ]
        try:
            self.ad.ldap.add_s(dn, mods)
        except ldap.SERVER_DOWN:
            self.ad.connect()
            self.create_container(name)

    __repr__ = name


class ADAccount(ADObject):
    """
    AD object representing a user.
    """

    # ===== Account options ====

    def is_enabled(self):
        """
        Is this account enabled?
        """
        return self.single_attribute("userAccountControl").decode() == str(UF_NORMAL_ACCOUNT)

    def enable(self):
        """
        Enable this account
        """
        self.set_single_attribute("userAccountControl", str(UF_NORMAL_ACCOUNT))

    def set_password(self, password):
        """
        Set the password of the user.
        """
        adpw = str('"' + password + '"')
        adpw = adpw.encode("utf-16-le")
        self.set_single_attribute("unicodePwd", adpw)

    def must_change_password(self):
        """
        After calling this the user needs to change their password the next time they login.
        """
        self.set_single_attribute("pwdLastSet", "0")  # user must change password

    def must_not_change_password(self):
        """
        After calling this the user does not need to change their password any more the next time they login.
        """
        self.set_single_attribute("pwdLastSet", "-1")  # user must not change password

    def has_changed_password(self):
        """
        Has this user already changed their password?
        """
        return int(self.single_attribute('pwdLastSet')) != 0

    def set_expiration(self, expiration_date):
        """
        Set the expiration date of this user account.
        """
        td = expiration_date - datetime.datetime(1601, 1, 1, tzinfo=utc)
        account_expires = (td.seconds + td.days * 24 * 3600) * 10 ** 7
        self.set_single_attribute("accountExpires", str(account_expires))

    def unset_expiration(self):
        """
        Unset the expiration date of this user account.
        """
        self.set_single_attribute("accountExpires", "0")

    # ==== Data queries ====

    def surname(self):
        """
        Get last name
        """
        surname = self.single_attribute('sn')
        return surname.decode() if surname else None

    def givenname(self):
        """
        Get first name
        """
        givenname = self.single_attribute('givenName')
        return givenname.decode() if givenname else None

    def shell(self):
        """
        Get unix shell
        """
        return self.single_attribute('loginShell').decode()

    # ==== Data commands ====

    def set_surname(self, sn):
        """
        Set last name
        """
        if sn:
            self.set_single_attribute('sn', sn)

    def set_givenname(self, gn):
        """
        Set first name
        """
        if gn:
            self.set_single_attribute('givenName', gn)

    def set_shell(self, shell):
        """
        Set unix shell
        """
        if shell:
            self.set_single_attribute('loginShell', shell)

    def set_account_name(self, name):
        super(ADAccount, self).set_account_name(name)
        domain = 'ia'
        self.set_single_attribute('userPrincipalName', '%s@%s' % (name, domain))

    def rename(self, newname):
        super(ADAccount, self).rename(newname)
        self.set_single_attribute('displayName', newname)


class ADGroup(ADObject):
    """
    AD object representing a group
    """

    def description(self):
        """
        Get group description
        """
        description = self.single_attribute('description')
        return description.decode() if description else None

    def set_description(self, descr):
        """
        Set group description
        """
        self.set_single_attribute('description', descr)

    def members(self):
        """
        Get list of group members
        """
        try:
            return [self.ad.get_object(member) for member in self.attrs['member']]
        except KeyError:
            return []  # no members

    def add_member(self, adobj):
        """
        Add member to group
        """
        self.add_multiple_attributes('member', adobj.dn)

    def delete_member(self, adobj):
        """
        Remove member from group
        """
        self.delete_multiple_attributes('member', adobj.dn)
