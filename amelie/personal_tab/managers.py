import datetime

from django.db import models
from django.db.models import Q
from django.db.models.aggregates import Sum
from django.utils import timezone

from amelie.members.models import Person


def _contribution_authorization_types():
    """
    Returns AuthorizationTypes solely for contributions.
    """
    from amelie.personal_tab.models import AuthorizationType
    return AuthorizationType.objects.filter(contribution=True, consumptions=False, activities=False)


def _people_with_outstanding_balance():
    """
    Returns a QuerySet with all Persons having a non-zero cookie corner balance.
    """
    # Date the SEPA debt collection went into effect: 2013-10-31 00:00 CET
    begin = datetime.datetime(2013, 10, 30, 23, 00, 00, tzinfo=timezone.utc)

    return Person.objects.filter(transaction__date__gte=begin).annotate(balance=Sum('transaction__price')).filter(
        balance__gt=0)


def _people_with_recent_or_future_transactions(days):
    """
    Returns a QuerySet with all Persons having recent or future transactions.
    """
    ninety_days_ago = timezone.now() - datetime.timedelta(days=days)
    return Person.objects.filter(transaction__date__gte=ninety_days_ago)


class AuthorizationManager(models.Manager):
    def contribution(self):
        """
        Return authorizations only used for membership fees.
        """
        return self.filter(authorization_type__in=_contribution_authorization_types())

    def non_contribution(self):
        """
        Return only authorizations not used for membership fees.
        """
        return self.exclude(authorization_type__in=_contribution_authorization_types())

    def contribution_to_terminate(self):
        """
        Return active but unused contribution authorizations which can be terminated.

        Uses the following requirements:
        - The person has not been a member for 180 days, or
        - The authorization is older than 720 days, there has not been a debt collection in those days,
          and there are no debt collections planned for this authorization.
        """
        from amelie.personal_tab.models import DebtCollectionInstruction

        ongoing_authorizations = self.contribution().filter(end_date__isnull=True)

        # The person has not been a member for 180 days
        not_a_member_for_half_a_year = ~Q(person__in=Person.objects.current_or_grace_period_membership())

        # The authorization is older than 720 days, there has not been a debt collection in those days,
        # and there are no debt collections planned.
        datetime_720_days_ago = timezone.now() - datetime.timedelta(days=720)
        no_recent_debt_collections_and_none_planned = Q(start_date__lt=datetime_720_days_ago) & ~Q(
            instructions__in=DebtCollectionInstruction.objects.recent_and_future(days=720)
        )

        return ongoing_authorizations.filter(not_a_member_for_half_a_year | no_recent_debt_collections_and_none_planned)

    def non_contribution_to_terminate(self):
        """
        Return active but unused non-contribution authorizations which can be terminated.

        Uses the following requirements:
        - There has not been any transaction or debt collection in the last 90 days, and
        - There are no future transactions planned, and
        - There is no outstanding balance, and
        - At least one of the following rules is met:
          - The person has not been a member for 180 days, or
          - The authorization is older than 720 days, there has not been a debt collection in those days,
            and there are no debt collections planned for this authorization.
        """
        from amelie.personal_tab.models import DebtCollectionInstruction

        authorizations = self.non_contribution().filter(end_date__isnull=True)

        # There has not been any transaction or debt collection in the last 90 days, and
        # There are no future transactions planned, and
        authorizations = authorizations.exclude(person__in=_people_with_recent_or_future_transactions(days=90))
        authorizations = authorizations.exclude(instructions__in=DebtCollectionInstruction.objects.recent_and_future(
            days=90
        ))

        # There is no outstanding balance, and
        outstanding_balance = list(_people_with_outstanding_balance())  # Force separate run of subquery
        authorizations = authorizations.exclude(person__in=outstanding_balance)

        # At least one of the following rules is met:
        # - The person has not been a member for 180 days, or
        # - The authorization is older than 720 days, there has not been a debt collection in those days,
        #   and there are no debt collections planned for this authorization.

        # The person has not been a member for 180 days, or
        not_a_member_for_half_a_year = ~Q(person__in=Person.objects.current_or_grace_period_membership())

        # The authorization is older than 720 days, there has not been a debt collection in those days,
        # and there are no debt collections planned for this authorization.
        datetime_720_days_ago = timezone.now() - datetime.timedelta(days=720)
        no_recent_debt_collections_and_none_planned = Q(start_date__lt=datetime_720_days_ago) & ~Q(
            instructions__in=DebtCollectionInstruction.objects.recent_and_future(days=720)
        )

        return authorizations.filter(not_a_member_for_half_a_year | no_recent_debt_collections_and_none_planned)

    def to_terminate(self):
        """
        Return active but unused authorizations which can be terminated.
        """
        return self.filter(Q(pk__in=self.contribution_to_terminate()) | Q(pk__in=self.non_contribution_to_terminate()))

    def contribution_to_anonymize(self):
        """
        Return inactive contribution authorizations which can be anonymized.

        Uses the following requirements:
        - The authorization has been terminated 60 days ago or longer, and
        - The last debt collection has occurred 500 days ago or longer, and no debt collections are planned.
        """
        from amelie.personal_tab.models import DebtCollectionInstruction

        # The authorization has not been anonymized yet.
        authorizations = self.contribution().filter(person__isnull=False)

        sixty_days_ago = timezone.now() - datetime.timedelta(days=60)

        # The authorization has been terminated 60 days ago or longer
        authorizations = authorizations.filter(end_date__lte=sixty_days_ago)

        # The last debt collection has occurred 500 days ago or longer, and no debt collections are planned.
        return authorizations.exclude(instructions__in=DebtCollectionInstruction.objects.recent_and_future(days=500))

    def non_contribution_to_anonymize(self):
        """
        Return inactive non-contribution authorizations which can be anonymized.

        Uses the following requirements:
        - The authorization has been terminated 60 days ago or longer, and
        - The last debt collection occurred 500 days ago or longer, and no debt collections are planned, and
        - There is no outstanding balance, and
        - There are no future transactions planned.
        """
        from amelie.personal_tab.models import DebtCollectionInstruction

        # The authorization has not been anonymized yet.
        authorization = self.non_contribution().filter(person__isnull=False)

        sixty_days_ago = timezone.now() - datetime.timedelta(days=60)

        # The authorization has been terminated 60 days ago or longer
        authorization = authorization.filter(end_date__lte=sixty_days_ago)

        # The last debt collection occurred 500 days ago or longer, and no debt collections are planned.
        authorization = authorization.exclude(instructions__in=DebtCollectionInstruction.objects.recent_and_future(days=500))

        # There is no outstanding balance
        outstanding_balance = list(_people_with_outstanding_balance())  # Force separate run of subquery
        authorization = authorization.exclude(person__in=outstanding_balance)

        # There are no future transactions planned.
        authorization = authorization.exclude(instructions__in=DebtCollectionInstruction.objects.recent_and_future(days=0))

        return authorization

    def to_anonymize(self):
        """
        Return inactive authorizations which can be anonymized.
        """
        return self.filter(Q(pk__in=self.contribution_to_anonymize()) |
                           Q(pk__in=self.non_contribution_to_anonymize()))


class DebtCollectionInstructionManager(models.Manager):
    def recent_and_future(self, days):
        """
        Return recent and future debt collection instructions.
        :param int days: Number of days to look back.
        """
        dt = timezone.now() - datetime.timedelta(days=days)
        return self.filter(batch__execution_date__gte=dt)
