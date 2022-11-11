from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.functional import cached_property
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

from amelie.members.models import Person


class RoomDutyPool(models.Model):
    """
    A pool of persons that can do room duties in a room duty table,
    for example the board or board+cb.
    """
    name = models.CharField(max_length=250, verbose_name=_("Name"))
    unsorted_persons = models.ManyToManyField(Person, related_name="room_duty_pools")

    @cached_property
    def persons(self):
        records = self.unsorted_persons.through.objects.filter(roomdutypool=self).order_by('id').prefetch_related('person')
        return [r.person for r in records]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Office duty")
        verbose_name_plural = _("Office duty pools")
        ordering = ['-name']


class RoomDutyTable(models.Model):
    """
    A set of room duties to fill in availability for, usually one week.
    """
    title = models.CharField(max_length=250, verbose_name=_("Title"))
    unsorted_pool = models.ManyToManyField(Person, related_name="room_duty_tables")
    begin = models.DateTimeField(verbose_name=_("Starts"))
    balcony_duty = models.ForeignKey("room_duty.BalconyDutyAssociation", null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.title

    @cached_property
    def persons(self):
        records = self.unsorted_pool.through.objects.filter(roomdutytable=self).order_by('id').prefetch_related('person')
        return [r.person for r in records]

    class Meta:
        verbose_name = _("Office duty schedule")
        verbose_name_plural = _("Office duty schedules")
        ordering = ['-begin']


class BalconyDutyAssociation(models.Model):
    association = models.CharField(max_length=255, verbose_name=_("Association"))
    is_this_association = models.BooleanField(verbose_name=_("Is Inter-Actief"))
    rank = models.PositiveIntegerField(unique=True)

    def __init__(self, *args, association=None, **kwargs):
        kwargs['rank'] = BalconyDutyAssociation.count() + 1
        super(BalconyDutyAssociation, self).__init__(*args, association=association, **kwargs)

    def __str__(self):
        return self.association

    @staticmethod
    def count():
        return BalconyDutyAssociation.objects.count()

    def swap(self, other):
        self.rank, other.rank = other.rank, self.rank

    def move_up(self):
        # Requires that this is not the first item
        other = BalconyDutyAssociation.objects.get(rank=self.rank-1)
        self.swap(other)

    def move_down(self):
        # Requires that this is not the last item
        other = BalconyDutyAssociation.objects.get(rank=self.rank+1)
        self.swap(other)

    def cycle_next(self):
        if self.rank == BalconyDutyAssociation.count():
            next = 1
        else:
            next = self.rank + 1

        return BalconyDutyAssociation.objects.get(rank=next)

    class Meta:
        ordering = ['rank']



class RoomDuty(models.Model):
    """
    One room duty, usually a morning or afternoon on a working day.
    """
    table = models.ForeignKey(RoomDutyTable, related_name="room_duties", on_delete=models.CASCADE)
    begin = models.DateTimeField(verbose_name=_('Starts'))
    end = models.DateTimeField(verbose_name=_('Ends'))

    participant_set = models.ManyToManyField(Person, blank=True, related_name="room_duties", verbose_name=_("Boardmembers"))

    update_count = models.PositiveIntegerField(default=0)

    def clean(self):
        super(RoomDuty, self).clean()

        if self.begin != None and self.end != None:
            if self.begin >= self.end:
                raise ValidationError(
                    {"begin": [_('Start may not be after of simultaneous to end.')]})

    # Properties for ical_event
    @property
    def summary(self):
        return "Room duty with {}".format(" & ".join(self.participant_names()))

    @property
    def description(self):
        return self.summary

    @property
    def location(self):
        return "Inter-/Actief/ room"

    @property
    def organizer(self):
        return None

    # Template helper functions
    def participant_names(self):
        return self.participant_set.values_list('first_name', flat=True)

    def availability_of(self, person):
        return RoomDutyAvailability(room_duty=self, person=person)

    def __str__(self):
        return _("Office duty from {begin} till {end}").format(
            begin=localtime(self.begin).strftime("%Y-%m-%d %H:%M:%S"),
            end=localtime(self.end).strftime("%Y-%m-%d %H:%M:%S"))

    def save(self, *args, **kwargs):
        self.update_count += 1
        super(RoomDuty, self).save(*args, **kwargs)

    class Meta:
        verbose_name = _("Office duty")
        verbose_name_plural = _("Office duties")
        ordering = ['begin', 'end']


class RoomDutyTableTemplate(models.Model):
    """
    A template for a room duty table, relative to a specified start,
    for example a regular week or an exam week.
    """
    title = models.CharField(max_length=250, verbose_name=_("Title"))

    @staticmethod
    def instantiate(template, title, pool, start_datetime, balcony_duty):
        table = RoomDutyTable.objects.create(title=title, begin=start_datetime, balcony_duty=balcony_duty)

        if pool is not None:
            for person in pool.persons:
                table.unsorted_pool.add(person)

        table.save()

        if template is not None:
            for room_duty_template in RoomDutyTemplate.objects.filter(table=template):
                room_duty = RoomDuty.objects.create(
                    table=table,
                    begin=start_datetime + room_duty_template.begin,
                    end=start_datetime + room_duty_template.end)
                room_duty.save()

        return table

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _("Office duty schedule template")
        verbose_name_plural = _("Office duty schedule templates")
        ordering = ['title']


class RoomDutyTemplate(models.Model):
    """
    One room duty from a room duty table template.
    """

    table = models.ForeignKey(RoomDutyTableTemplate, related_name="room_duties", on_delete=models.CASCADE)

    begin = models.DurationField(verbose_name=_("Starts"))
    end = models.DurationField(verbose_name=_("Ends"))

    def __str__(self):
        begin = self.begin
        end = self.end

        dfrom = int(begin.total_seconds() // timedelta(days=1).total_seconds())
        begin -= timedelta(days=1) * dfrom

        dto = int(end.total_seconds() // timedelta(days=1).total_seconds())
        end -= timedelta(days=1) * dto

        hfrom = int(begin.total_seconds() // timedelta(hours=1).total_seconds())
        begin -= timedelta(hours=1) * hfrom

        hto = int(end.total_seconds() // timedelta(hours=1).total_seconds())
        end -= timedelta(hours=1) * hto

        mfrom = int(begin.total_seconds() // timedelta(minutes=1).total_seconds())
        mto = int(end.total_seconds() // timedelta(minutes=1).total_seconds())

        return _("Day {dfrom}, {hfrom:02d}:{mfrom:02d} till day {dto}, {hto:02d}:{mto:02d}").format(
            dfrom=dfrom,
            dto=dto,
            hfrom=hfrom,
            hto=hto,
            mfrom=mfrom,
            mto=mto,
        )

    class Meta:
        verbose_name = _("Office duty template")
        verbose_name_plural = _("Office duty templates")
        ordering = ['begin', 'end']


class RoomDutyAvailability(models.Model):
    class Availabilities(models.TextChoices):
        DIBS = 'D', _("Dibs!")
        GLADLY = 'G', _("Yes please!")
        AVAILABLE = 'O', _("Available")
        RATHER_NOT = '#', _("Rather not")
        UNAVAILABLE = 'X', _("No, sorry")
        UNKNOWN = '?', _("Not sure yet")

    room_duty = models.ForeignKey(RoomDuty, related_name="availabilities", on_delete=models.CASCADE)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)

    availability = models.CharField(max_length=1, choices=Availabilities.choices, default=Availabilities.UNKNOWN)
    hungover = models.BooleanField(default=False)
    not_in_the_break = models.BooleanField(default=False)

    comments = models.CharField(blank=True, max_length=250, verbose_name=_("Comments"))

    @property
    def css_class(self):
        mapping = {
            RoomDutyAvailability.Availabilities.DIBS.value: "room-duty-dibs",
            RoomDutyAvailability.Availabilities.GLADLY.value: "room-duty-gladly",
            RoomDutyAvailability.Availabilities.AVAILABLE.value: "room-duty-available",
            RoomDutyAvailability.Availabilities.RATHER_NOT.value: "room-duty-rather-not",
            RoomDutyAvailability.Availabilities.UNAVAILABLE.value: "room-duty-unavailable",
            RoomDutyAvailability.Availabilities.UNKNOWN.value: "room-duty-unknown",
        }

        return mapping[self.availability]

    class Meta:
        verbose_name = _("Office duty availability")
        verbose_name_plural = _("Office duty availabilities")

