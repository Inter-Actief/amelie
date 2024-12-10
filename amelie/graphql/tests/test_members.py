import json
import datetime
import random
from typing import Dict

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from amelie.members.models import Committee, CommitteeCategory
from amelie.graphql.tests import BaseGraphQLPrivateFieldTests


def generate_committees():
    """
    Generate Committees for testing.

    It will generate a committee category and 4 committees:
    - A regular committee without parent
    - A regular committee with a parent
    - An abolished committee without a parent
    - An abolished committee with a parent
    """

    cc = CommitteeCategory.objects.create(name="Committee Category", slug="committee-category")

    now = datetime.date.today()
    last_week = now - datetime.timedelta(days=7)

    for abolished in [True, False]:
        committee = Committee.objects.create(
            name=f"Committee {'Abolished' if abolished else 'Regular'}",
            abbreviation=f"c-{'abolished' if abolished else 'regular'}",
            category=cc,
            slug=f"committee-{'abolished' if abolished else 'regular'}",
            email=f"committee-{'abolished' if abolished else 'regular'}@inter-actief.net",
            founded=last_week,
            abolished=now if abolished else None,
            website="https://inter-actief.net",
            information_nl="Informatie NL",
            information_en="Information En",
            private_email=abolished,
            superuser=False,
            gitlab=False,
            logo=SimpleUploadedFile("logo.jpg", b"File Contents"),
            group_picture=SimpleUploadedFile("group.jpg", b"File Contents"),
            ledger_account_number="1111"
        )
        child_committee = Committee.objects.create(
            name=f"Child Committee {'Abolished' if abolished else 'Regular'}",
            abbreviation=f"cc-{'abolished' if abolished else 'regular'}",
            category=cc,
            slug=f"child-committee-{'abolished' if abolished else 'regular'}",
            email=f"childcommittee-{'abolished' if abolished else 'regular'}@inter-actief.net",
            founded=last_week,
            abolished=now if abolished else None,
            website="https://inter-actief.net",
            information_nl="Informatie NL",
            information_en="Information En",
            private_email=abolished,
            superuser=False,
            gitlab=False,
            logo=SimpleUploadedFile("logo.jpg", b"File Contents"),
            group_picture=SimpleUploadedFile("group.jpg", b"File Contents"),
            ledger_account_number="1111"
        )
        child_committee.parent_committees.add(committee)



class MembersGraphQLPrivateFieldTests(BaseGraphQLPrivateFieldTests):
    """
    Tests for private fields of models of the Members app

    Queries:
    - committeeCategory
    - committeeCategories
    - committee
    - committees
    """

    def setUp(self):
        super(MembersGraphQLPrivateFieldTests, self).setUp()

        # Generate committees
        generate_committees()

        # Retrieve those committees
        self.category = CommitteeCategory.objects.get(slug="committee-category")
        self.regular_committee = Committee.objects.get(abbreviation="c-regular")
        self.abolished_committee = Committee.objects.get(abbreviation="c-abolished")
        self.regular_child_committee = Committee.objects.get(abbreviation="cc-regular")
        self.abolished_child_committee = Committee.objects.get(abbreviation="cc-abolished")


    MEMBERS_COMITTEE_PRIVATE_FIELDS: Dict[str, str] = {
        "abbreviation": "abbreviation",
        "private_email": "privateEmail",
        "superuser": "superuser",
        "gitlab": "gitlab",
        "ledger_account_number": "ledgerAccountNumber",

        # function_set private subfields
        "function_set.note": "functionSet { note }",

        # parent_committees private subfields
        "parent_committees.abbreviation": "parentCommittees { abbreviation }",
        "parent_committees.private_email": "parentCommittees { privateEmail }",
        "parent_committees.superuser": "parentCommittees { superuser }",
        "parent_committees.gitlab": "parentCommittees { gitlab }",
        "parent_committees.ledger_account_number": "parentCommittees { ledgerAccountNumber }",
        "parent_committees.function_set.note": "parentCommittees { functionSet { note } }",
    }
    # TODO: email field if private_email is set for committee

    MEMBERS_COMITTEECATEGORY_PRIVATE_FIELDS: Dict[str, str] = {
        "committee_set.": "callbackUrl",
        "committee_set.abbreviation": "committeeSet { abbreviation }",
        "committee_set.private_email": "committeeSet { privateEmail }",
        "committee_set.superuser": "committeeSet { superuser }",
        "committee_set.gitlab": "committeeSet { gitlab }",
        "committee_set.ledger_account_number": "committeeSet { ledgerAccountNumber }",

        # function_set private subfields
        "committee_set.function_set.note": "committeeSet { functionSet { note } }",

        # parent_committees private subfields
        "committee_set.parent_committees.abbreviation": "committeeSet { parentCommittees { abbreviation } }",
        "committee_set.parent_committees.private_email": "committeeSet { parentCommittees { privateEmail } }",
        "committee_set.parent_committees.superuser": "committeeSet { parentCommittees { superuser } }",
        "committee_set.parent_committees.gitlab": "committeeSet { parentCommittees { gitlab } }",
        "committee_set.parent_committees.ledger_account_number": "committeeSet { parentCommittees { ledgerAccountNumber } }",
        "committee_set.parent_committees.function_set.note": "committeeSet { parentCommittees { functionSet { note } } }",
    }

    def test_committee_private_model(self):
        # Test if abolished committees cannot be retrieved
        self._test_private_model(
            query_name="committee",
            variables={"id": (self.abolished_committee.id, "ID")}
        )
        self._test_private_model(
            query_name="committee",
            variables={"id": (self.abolished_child_committee.id, "ID")}
        )

    def test_committees_private_model(self):
        # Test if abolished committees cannot be retrieved via list view
        self._test_private_model_list(
            query_name="committees",
            public_field_spec="results { id }",
            variables={"id": (self.abolished_committee.id, "ID"), "includeAbolished": (True, "Boolean!")}
        )
        self._test_private_model_list(
            query_name="committees",
            public_field_spec="results { id }",
            variables={"id": (self.abolished_child_committee.id, "ID"), "includeAbolished": (True, "Boolean!")}
        )

    def test_committee_private_fields(self):
        # Test if private fields on regular committees cannot be retrieved
        for field_name, field_spec in self.MEMBERS_COMITTEE_PRIVATE_FIELDS.items():
            self._test_public_model_and_private_field(
                query_name="committee", field_name=field_name, field_spec=field_spec,
                variables={"id": (self.regular_committee.id, "ID")},
            )
            self._test_public_model_and_private_field(
                query_name="committee", field_name=field_name, field_spec=field_spec,
                variables={"id": (self.regular_child_committee.id, "ID")},
            )

    def test_committees_private_fields(self):
        # Test if private fields on regular committees cannot be retrieved via list view
        for field_name, field_spec in self.MEMBERS_COMITTEE_PRIVATE_FIELDS.items():
            # Wrap the field spec in "results { <SPEC> }" for list view
            field_spec = f"results {{ {field_spec} }}"
            self._test_public_model_and_private_field(
                query_name="committees", field_name=field_name, field_spec=field_spec,
                variables={"id": (self.regular_committee.id, "ID"), "includeAbolished": (True, "Boolean!")}
            )
            self._test_public_model_and_private_field(
                query_name="committees", field_name=field_name, field_spec=field_spec,
                variables={"id": (self.regular_child_committee.id, "ID"), "includeAbolished": (True, "Boolean!")}
            )

    def test_committee_category_private_fields(self):
        # Test if private fields on committee categories cannot be retrieved
        for field_name, field_spec in self.MEMBERS_COMITTEECATEGORY_PRIVATE_FIELDS.items():
            self._test_public_model_and_private_field(
                query_name="committeeCategory", field_name=field_name, field_spec=field_spec,
                variables={"id": (self.category.id, "ID")},
            )

    def test_committee_categories_private_fields(self):
        # Test if private fields on committee categories cannot be retrieved via list view
        for field_name, field_spec in self.MEMBERS_COMITTEECATEGORY_PRIVATE_FIELDS.items():
            # Wrap the field spec in "results { <SPEC> }" for list view
            field_spec = f"results {{ {field_spec} }}"
            self._test_public_model_and_private_field(
                query_name="committeeCategories", field_name=field_name, field_spec=field_spec,
                variables={"id": (self.category.id, "ID")}
            )
