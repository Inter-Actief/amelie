import functools
import sys
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse, NoReverseMatch, resolve
from django.utils import timezone

from amelie.members.models import Person, Committee, Function, MembershipType, Membership, CommitteeCategory
from amelie.personal_tab.models import DiscountPeriod, Article

# Ignore all names starting with. No namespaces can be added here, so be sure you are not ignoring more than intended.
IGNORE_NAMES_STARTING = ["admin-", "django-admindocs-"]

# Ignore these namespaces.
IGNORE_NAMESPACES = ["admin", "djdt", "api", "djangosaml2idp"]

# These specific names will not be tested at all.
IGNORE_NAMES = [
    "legacy_logout",  # May break some tests if the client is no longer logged in.
    "statistics:statistics",  # TODO add transactions to test this one
    "members:data_export",  # Does not allow GET-requests, only POST.
    "activities:photos",  # No pictures in the test database, so the paginator breaks

    "personal_tab:print_index",  # Needs a paper article in the cookie corner with a specific ID.

    # SAML URLs do not need to work in development
    "saml2_acs", "saml2_login", "saml2_logout", "saml2_ls", "saml2_ls_post", "saml2_metadata",

    # Cannot test OIDC login
    "oidc_authentication_callback", "oidc_authentication_init", "oidc_logout",

    # Captcha library urls don't need to be checked
    "captcha-image", "captcha-image-2x", "captcha-audio", "captcha-refresh",

    # UserInfo / GroupInfo API endpoints need extra configuration
    "members:person_userinfo", "members:person_groupinfo",

    # GSuite forwarding views don't need to work in development
    "account:activate_forwarding_address", "account:add_forwarding_address", "account:check_forwarding_status",
    "account:check_forwarding_verification", "account:deactivate_forwarding_address",

    # Uses YouTube API credentials / relies on external service, does not need to work in development
    "videos:new_yt_video", "videos:new_ia_video",

    # Room narrowcasting page uses Spotify and Icinga API that is not configured in development.
    "narrowcasting:room_pcstatus", "narrowcasting:room_spotify_callback", "narrowcasting:room_spotify_now_playing",
]

# These pages should not cause Exceptions, but will not be checked for a 302 or 200 (namespaces must be prepended).
IGNORE_RESULT = [
    "token", "authorize", "ckeditor_upload", "oauth2:token",
    "personal_tab:pos_process", "members:autocomplete", "members:autocomplete_cookie_corner",
    "activities:random_photo",  # Media folder may not be working, so will not test it.
]

# Names or urls of which the redirects should be followed (namespaces must be prepended).
REDIRECTS_FOLLOW = [
    "frontpage", "members:query", "legacy_login", "set_language", "personal_tab:my_dashboard", "/"
]

# Names or urls that should at least redirect (namespaces must be prepended).
REDIRECTS = REDIRECTS_FOLLOW + [
    "favicon_redirect",  # Static files can't be checked, so we will just
    "personal_tab:pos_logout", "personal_tab:pos_register_external", "personal_tab:pos_scan_external",
    "personal_tab:pos_shop", "personal_tab:register_scan", "personal_tab:my_dashboard",
    "account:password_reset", "account:password_reset_success"
]


class AllUrlsTestCase(TestCase):
    """
    Tests of this class are generated, so do NOT add your own as they will possibly be replaced by generated ones.

    Only urls with no arguments required will be tested.
    """
    def sub_test_url(self, name, url=None):
        """
        Will test a given name (like "members:query"). It will just check for a 200 or a 302 depending on the constants
        above.
        :param name: The name of the page to test, will just be used for logging if an url is provided.
        :param url: Optionally specify an url to override the name attribute.
        :return:
        """
        try:
            # Only reverse the url if none is given
            if url:
                url_reversed = url
            else:
                url_reversed = reverse(name)
            url_resolved = resolve(url_reversed)
        except NoReverseMatch:
            pass
        else:
            try:
                response = self.get_client().get(url_reversed)
                if (url or name not in IGNORE_RESULT) and url not in IGNORE_RESULT:
                    if (not url and name in REDIRECTS) or url in REDIRECTS or getattr(
                            url_resolved.func, '__name__', None) == 'RedirectView':
                        self.assertEqual(
                            response.status_code, 302,
                            'This page should redirect: {} ({}). {}'.format(name, url_reversed,
                                                                            response.content)
                        )
                        if (not url and name in REDIRECTS_FOLLOW) or url in REDIRECTS_FOLLOW:
                            self.sub_test_url(name, response.url)
                    else:
                        self.assertEqual(
                            response.status_code, 200,
                            'Could not open: {} ({}) {}\n{}'.format(
                                name, url_reversed, getattr(response, 'url', ''), response.content
                            )
                        )
            except:  # Add more logging if the test fails.
                sys.stderr.write('[Error on: "{}" (url="{}")]'.format(name, url_reversed))
                sys.stderr.flush()
                raise

    @functools.lru_cache()
    def get_client(self):
        """
        Create all the necessary objects in the database.
        :return:
        """
        django_user = User.objects.create(
            username='account_name', first_name='first_name', is_staff=True, is_superuser=True
        )
        user = Person.objects.create(
            first_name='first_name', last_name_prefix='between_additive', last_name='last_name', initials='initials',
            slug='first_name', gender=Person.GenderTypes.UNKNOWN, address='address field', postal_code='1234 AB',
            city='living_place', country='country', email_address='a@a.com', telephone='telephone_number',
            account_name='account_name', webmaster=True, user=django_user,
        )

        # Board like committee. Needed to visit all pages.
        committee = Committee.objects.create(
            abbreviation="abbrr", email='', abolished=None, website='', name='NAME',
            information_nl='informatie over deze commissie', information_en='info about this committee', logo=None,
            group_picture=None, ledger_account_number='2500', superuser=True
        )
        Function.objects.create(
            person=user, committee=committee, function='function of person', note='Remark?',
            begin=timezone.now() - timedelta(days=10), end=None,
        )

        # To make the committee page work (breaks if none exist)
        category = CommitteeCategory.objects.create(name='pudding')
        committee = Committee.objects.create(  # MediaCie to make the video module work
            abbreviation="MediaCie", email='', abolished=None, website='', name='MedIA Committee',
            information_nl='informatie over deze MedIA-commissie', information_en='info about this MedIA committee', logo=None,
            group_picture=None, ledger_account_number='2500', superuser=False, category=category
        )
        Function.objects.create(
            person=user, committee=committee, function='function of MedIA committee person', note='Remark?',
            begin=timezone.now() - timedelta(days=10), end=None,
        )

        # Create Vivat committee for publications app
        Committee.objects.create(
            abbreviation="Vivat", email='', abolished=None, website='', name='Vivat',
            information_nl='informatie over deze Vivat', information_en='info about this Vivat', logo=None,
            group_picture=None, ledger_account_number='2500', superuser=False, category=category
        )

        # Create KasCo comittee for company statistics page
        Committee.objects.create(
            abbreviation="KasCo", email='', abolished=None, website='', name='Audit',
            information_nl='Informatie over deze KasCo', information_en='Info about this KasCo', logo=None,
            group_picture=None, ledger_account_number='2500', superuser=False, category=category
        )

        # So that the statistics pages work
        MembershipType.objects.bulk_create([
            MembershipType(
                name_nl='inbitween', name_en='name_en', description='VERY EXPENSIVE', price=100, active=True
            ),
            MembershipType(
                name_nl='Donateur', name_en='name_en', description='VERY EXPENSIVE', price=100, active=True
            ),
            MembershipType(
                name_nl='Studielang (vervolg)', name_en='Studylong (continuation)', description='VERY EXPENSIVE',
                price=100, active=True
            ),
            MembershipType(
                name_nl='Erelid', name_en='name_en', description='VERY EXPENSIVE', price=100, active=True
            ),
            MembershipType(
                name_nl='Studielang (eerste jaar)', name_en='Studylong (first year)', description='VERY EXPENSIVE', price=100,
                active=True
            ),
            MembershipType(
                name_nl='inbitween (studielang)', name_en='name_en', description='VERY EXPENSIVE', price=100,
                active=True
            ),
            MembershipType(
                name_nl='Lid van verdienste', name_en='name_en', description='VERY EXPENSIVE', price=100, active=True
            ),
            MembershipType(
                name_nl='Medewerker jaar', name_en='Employee yearlong', description='VERY EXPENSIVE', price=100, active=True
            ),
            MembershipType(
                name_nl='Primair jaarlid', name_en='Primary yearlong', description='VERY EXPENSIVE', price=100, active=True
            ),
            MembershipType(
                name_nl='Secundair jaarlid', name_en='Secondary yearlong', description='VERY EXPENSIVE', price=100, active=True
            ),
        ])
        # So that pool committees can be calculated
        CommitteeCategory.objects.create(name="Pools")

        # So that the user is actually a member (fixes statistics)
        Membership.objects.bulk_create([
            Membership(member=user, type=MembershipType.objects.get(name_nl='Studielang (vervolg)'),
                       year=timezone.now().year - 1),
            Membership(member=user, type=MembershipType.objects.get(name_nl='Studielang (vervolg)'),
                       year=timezone.now().year),
            Membership(member=user, type=MembershipType.objects.get(name_nl='Studielang (vervolg)'),
                       year=timezone.now().year + 1),
        ])

        # To make exam credits work
        DiscountPeriod.objects.create(
            id=settings.COOKIE_CORNER_EXAM_COOKIE_DISCOUNT_PERIOD_ID, begin=timezone.now() - timedelta(days=1500),
            end=None, description_nl='Tentamenkoeken', description_en='Exam credits',
            ledger_account_number='2500', balance_account_number='2500',
        )

        # TODO create transaction to test
        # StreeplijstTransactie.objects.create(
        #     artikel=None,
        #     aantal=100,
        # )

        # Now let us create a client and have it login
        result = Client()
        result.force_login(django_user)
        return result


def load_url_pattern_names(pattern):
    """
    Returns all the names of the pages. Will also contain those that require extra arguments to reverse.

    Namespaces in IGNORE_NAMESPACES will be ignored.

    All names (without namespaces prepended) starting with a string from IGNORE_NAMES_STARTING will be ignored.

    :param pattern: The top url pattern. Should be "__import__(settings.ROOT_URLCONF).urls" or one of its children.
    :return: A list of strings containing the names of all pages (namespaces are prepended where needed (members:query)).
    """
    result = set()
    for pat in pattern:
        if pat.__class__.__name__ == 'URLResolver':
            # load patterns from this URLResolver
            if pat.namespace:
                if pat.namespace not in IGNORE_NAMESPACES:  # Ignore namespaces
                    sub_urls = load_url_pattern_names(pat.url_patterns)
                    result = result.union(map(lambda x: '{}:{}'.format(pat.namespace, x), sub_urls))
            else:
                result = result.union(load_url_pattern_names(pat.url_patterns))
        elif pat.__class__.__name__ == 'URLPattern':
            # load name from this URLPattern
            if pat.name is not None and not any(pat.name.startswith(x) for x in IGNORE_NAMES_STARTING):  # ignore stuff
                result.add(pat.name)
        else:
            print(f"Unknown pattern class: {pat.__class__.__name__} in url config, pattern: {pat}", file=sys.stderr)
    return result


# Load all names
urls_module = __import__(settings.ROOT_URLCONF).urls
page_names = load_url_pattern_names(urls_module.urlpatterns)

for page_name in list(page_names):
    if page_name not in IGNORE_NAMES: # filter full names
        # Set the tests of AllUrlsTestCase
        setattr(AllUrlsTestCase, 'test_{}'.format(page_name.replace(':', '__')),
                (lambda x_url: (lambda self: self.sub_test_url(x_url)))(page_name))
