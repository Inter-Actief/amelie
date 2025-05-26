import datetime
import random

from django.conf import settings
from django.db.models import Sum, Q
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from amelie.members.models import Study, Student
from amelie.personal_tab.models import ActivityTransaction, DiscountPeriod, DiscountCredit, CookieCornerTransaction, \
    Discount
from amelie.tools.logic import current_academic_year_strict


def person_remove():
    # TODO
    pass


def participation_transaction(participation, reason, cancel=False, added_by=None):
    """
    Helper function that adds an ActivityTransaction.

    participation:  Object to generate a transaction for.
    reason:         Reason/description of this transaction
    cancel:         If True, make a compensation for a participation. This requires the participation.pk != None.
    added_by:       Who created the transaction.
    """

    # Take the begin date/time as the date of the transaction, unless this moment has already passed. Jelte 2013-09-25
    date = max(participation.event.begin, timezone.now())

    if cancel:
        try:
            # The latest (by create time) positive ActivityTransaction for this participation should be compensated
            old_transaction = ActivityTransaction.objects.filter(
                participation=participation, event=participation.event, person=participation.person,
                price__gte=0  # Positive (or 0) price
            ).order_by('-added_on').first()  # Latest transaction, by creation time
        except ActivityTransaction.DoesNotExist:
            # A compensation does not need to be created because there is no transaction to compensate.
            return

        price = -1 * old_transaction.price
        with_enrollment_options = old_transaction.with_enrollment_options
    else:
        price, with_enrollment_options = participation.calculate_costs()

    # Create transaction
    transaction = ActivityTransaction(price=price, description=reason, participation=participation,
                                      event=participation.event, person=participation.person, date=date,
                                      with_enrollment_options=with_enrollment_options, added_by=added_by)

    # And save
    transaction.save()


def add_participation(participation, added_by=None, is_edited_participation=False):
    """Adds a transaction for a participation in an event."""

    with translation.override(participation.person.preferred_language):
        if is_edited_participation:
            reason = _("Edited enrollment for {activity} (addition of updated costs)").format(activity=participation.event.summary)
        else:
            reason = _("Enrolled for {activity}").format(activity=participation.event.summary)

    participation_transaction(participation, reason, added_by=added_by)


def remove_participation(participation, added_by=None, is_edited_participation=False):
    """Adds a transaction to nullify a participation in an event."""

    with translation.override(participation.person.preferred_language):
        if is_edited_participation:
            reason = _("Edited enrollment for {activity} (reversal of old costs)").format(activity=participation.event.summary)
        else:
            reason = _("Unenrolled for {activity}").format(activity=participation.event.summary)

    participation_transaction(participation, reason, cancel=True, added_by=added_by)


def exam_cookie_discount():
    """Return the DiscountPeriod for the Exam Cookie discount."""
    return DiscountPeriod.objects.get(id=settings.COOKIE_CORNER_EXAM_COOKIE_DISCOUNT_PERIOD_ID)


def exam_cookie_credit(person):
    """Return the current exam cookie credit of a person."""
    discount_period = exam_cookie_discount()
    discount_credits = person.discountcredit_set.filter(discount_period=discount_period)
    return discount_credits.aggregate(Sum('price'))['price__sum']


def add_exam_cookie_credit(price, person, description, added_by):
    """Increase the exam cookie credit with the given amount."""
    discount_period = exam_cookie_discount()

    discount_credit = DiscountCredit(discount_period=discount_period, date=timezone.now(), price=price, person=person,
                                     description=description, added_by=added_by)
    discount_credit.save()

    return discount_credit


def cookie_corner_sale(article, amount, person, added_by):
    """Register a sale in the cookie corner.

    Make sure you call this method only from within a database transaction!
    :type article: Article
    :type amount: int
    :type person: Person
    :type added_by: Person
    """
    now = timezone.now()

    if amount < 0:
        raise ValueError("Someone is trying to get money by buying a negative number of products!")

    with translation.override(person.preferred_language):
        description = _(u"Sale {category}::{article}").format(category=article.category.name,
                                                              article=article.name)
    total_price = amount * article.price

    discount_period = exam_cookie_discount()
    cookie_credit = person.discountcredit_set.select_for_update().filter(discount_period=discount_period
                                                                         ).aggregate(Sum('price'))['price__sum']

    discount = None

    if cookie_credit is None:
        cookie_credit = 0

    # TODO Check if exam cookies are allowed
    if cookie_credit > 0 and total_price > 0 and article in discount_period.articles.all():
        discount_amount = min(cookie_credit, total_price)
        total_price -= discount_amount

        # Register discount
        discount = Discount(amount=discount_amount, date=now, discount_period=discount_period)
        discount.save()

        # Register usage of credit
        DiscountCredit(discount_period=discount_period, date=now, price=-discount_amount, person=person,
                       description=description, discount=discount, added_by=added_by).save()

    transaction = CookieCornerTransaction(date=now, price=total_price, person=person, description=description,
                                          discount=discount, article=article, amount=amount, added_by=added_by)
    transaction.save()
    return transaction


def free_cookie_discount():
    """Return the DiscountPeriod for the free cookie discount."""
    return DiscountPeriod.objects.get(id=settings.COOKIE_CORNER_FREE_COOKIE_DISCOUNT_PERIOD_ID)


def free_cookie_is_winner(person):
    """Determine if the given person is a winner based on the configured chances."""
    now = timezone.now()
    discount_period = free_cookie_discount()

    if now < discount_period.begin or (discount_period.end and now > discount_period.end):
        # Discount period is not running at this moment.
        return False

    main_studies = Study.objects.filter(primary_study=True)
    bsc_main_studies = main_studies.filter(type='BSc')
    msc_main_studies = main_studies.filter(type='MSc')
    date = datetime.date(current_academic_year_strict() - 2, 9, 1)

    primary_study_member = Student.objects.filter(person=person, studyperiod__study__in=main_studies).exists()

    if not primary_study_member:
        return False

    older_years = Student.objects.filter(
        Q(studyperiod__study__in=bsc_main_studies, studyperiod__begin__lte=date) | Q(
            studyperiod__study__in=msc_main_studies
        ), person=person
    ).exists()

    if older_years:
        chance = settings.COOKIE_CORNER_FREE_COOKIE_DISCOUNT_RATE_HIGH
    else:
        chance = settings.COOKIE_CORNER_FREE_COOKIE_DISCOUNT_RATE_LOW

    if random.random() > chance:
        # Did not win
        return False

    already_used = discount_period.discount_set.all().aggregate(Sum('amount'))['amount__sum'] or 0
    if already_used >= settings.COOKIE_CORNER_FREE_COOKIE_DISCOUNT_LIMIT:
        # Limit has been reached
        return False

    # You won!
    return True


def free_cookies_allowed(article):
    discount_period = free_cookie_discount()
    articles = discount_period.articles.all()
    return article in articles


def free_cookies_sale(article, amount, person, added_by):
    """
    Register a sale in the cookie corner with the free cookie discount.

    Make sure you run this function only in a database transaction!

    :type article: Article
    :type amount: int
    :type person: Person
    :type added_by: Person
    """
    now = timezone.now()

    with translation.override(person.preferred_language):
        description = _(u"Sale {category}::{article}").format(category=article.category.name,
                                                                 article=article.name)
    total_price = amount * article.price

    discount_period = free_cookie_discount()

    discount_amount = article.price
    total_price -= discount_amount

    # Register discount
    discount = Discount(amount=discount_amount, date=now, discount_period=discount_period)
    discount.save()

    transaction = CookieCornerTransaction(date=now, price=total_price, person=person, description=description,
                                          discount=discount, article=article, amount=amount, added_by=added_by)
    transaction.save()
    return transaction
