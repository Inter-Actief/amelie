import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils.encoding import smart_str

from amelie.iamailer.mailtask import MailTask
from amelie.members.management.commands.dataupdatemail import dataupdate_context
from amelie.members.models import Payment, PaymentType, Membership, MembershipType
from amelie.personal_tab.debt_collection import authorization_contribution
from amelie.tools.mail import PersonRecipient


class Command(BaseCommand):
    help = "Transfer the memberships from from_year to to_year."

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser=parser)
        parser.add_argument('from_year')
        parser.add_argument('to_year')
        parser.add_argument(
            '--prolong-late',
            dest='prev_prolong',
            help='Use if this is not the first time this year to run the command',
            default=False,
            action='store_true'
        )
        parser.add_argument(
            '--commit',
            action='store_true',
            dest='commit',
            default=False,
            help='Save changes'
        )

    def handle(self, *args, **options):
        prev_prolong = options['prev_prolong']
        commit = options['commit']
        if not commit:
            self.stderr.write('** TEST MODE **')
            self.stderr.write('Add --commit to save changes')

        try:
            current_year = int(options['from_year'])
            new_year = int(options['to_year'])
        except ValueError:
            raise CommandError("Type numbers for years...")


        # These memberships are automatically prolonged without change,
        # unless the membership was terminated by the member
        yearmembershiptypes_text = [
            'Donateur',
            'Erelid',
            'Lid van verdienste',
            'Medewerker jaar',
            'Primair jaarlid',
            'Secundair jaarlid',
        ]

        # ENIAC membership
        ENIAC_MEMBERSHIP_TEXT = 'ENIAC'
        ENIAC_MEMBERSHIP = MembershipType.objects.get(name_nl=ENIAC_MEMBERSHIP_TEXT)

        # These memberships are automatically prolonged, unless the membership was terminated by the member,
        # or the member is no longer enrolled for one of the base studies (is not verified by signing in via UT SAML)
        studylongmembershiptypes_text = [
            'Studielang (eerste jaar)',
            'Studielang (vervolg)',
        ]

        yearmembershiptypes = MembershipType.objects.filter(name_nl__in=yearmembershiptypes_text)
        studylongmembershiptypes = MembershipType.objects.filter(name_nl__in=studylongmembershiptypes_text)

        # By default the next membership type is the same as the current one.
        next_membership_type = dict((lt, lt) for lt in MembershipType.objects.all())

        # Study long (first year) membership is replaced by Study long (continuation)
        studylong_firstyear = MembershipType.objects.get(name_nl='Studielang (eerste jaar)')
        studylong_continuation = MembershipType.objects.get(name_nl='Studielang (vervolg)')
        next_membership_type[studylong_firstyear] = studylong_continuation

        # The members that will be in this file have not automatically gotten a new membership.
        discontinued_members_file = open('discontinued.txt', 'w')
        # This file will hold all errors. For these people nothing is created. The reason is also in the file.
        errorfile = open('errorfile.txt', 'w')

        continuationmails = MailTask(from_='I.C.T.S.V. Inter-Actief <secretaris@inter-actief.net>',
                                     template_name='members/yeartransfer_prolonged.mail',
                                     report_to='I.C.T.S.V. Inter-Actief <secretaris@inter-actief.net>',
                                     report_language='nl',
                                     report_always=True)
        discontinuationmails_first = MailTask(from_='I.C.T.S.V. Inter-Actief <secretaris@inter-actief.net>',
                                        template_name='members/yeartransfer_ended.mail',
                                        report_to='I.C.T.S.V. Inter-Actief <secretaris@inter-actief.net>',
                                        report_language='nl',
                                        report_always=True)

        discontinuationmails_final = MailTask(from_='I.C.T.S.V. Inter-Actief <secretaris@inter-actief.net>',
                                        template_name='members/yeartransfer_ended_final.mail',
                                        report_to='I.C.T.S.V. Inter-Actief <secretaris@inter-actief.net>',
                                        report_language='nl',
                                        report_always=True)

        discontinuationmails_eniac = MailTask(from_='I.C.T.S.V. Inter-Actief <secretaris@inter-actief.net>',
                                              template_name='members/yeartransfer_ended_eniac.mail',
                                              report_to='I.C.T.S.V. Inter-Actief <secretaris@inter-actief.net>',
                                              report_language='nl',
                                              report_always=True)

        paymenttype_continuation = PaymentType.objects.filter(name='Studielang (vervolg)')[0]
        paymenttype_sponsored = PaymentType.objects.filter(name='Sponsoring')[0]

        error_already_enrolled = u"{} ({}) was already enrolled for the new year, no payment was created!\n"

        if prev_prolong:
            memberships = Membership.objects.filter(year=current_year, type__needs_verification=True)
        else:
            memberships = Membership.objects.filter(year=current_year)

        for membership in memberships:
            if not membership.ended:
                next_type = next_membership_type[membership.type]

                prolong = False
                payment_type = None

                if membership.type in yearmembershiptypes:
                    prolong = True
                    if next_type.price == Decimal("0.00"):
                        payment_type = paymenttype_sponsored

                elif membership.type in studylongmembershiptypes and membership.is_verified():
                    prolong = True
                    payment_type = paymenttype_continuation

                # Check if there actually is a new membership already,
                # and set prolong to True if it was not yet, so they get a prolongation mail instead of a discontinuation mail.
                already_exists = False
                try:
                    new_membership = Membership.objects.get(member=membership.member, year=new_year, ended__isnull=True)
                except Membership.DoesNotExist:
                    pass
                else:
                    next_type = new_membership.type
                    prolong = True
                    already_exists = True

                if prolong:
                    if already_exists:
                        self.stdout.write(u"{} ({}) -> {} (already existed)".format(membership.member, membership.type,
                                                                                    next_type))
                    else:
                        self.stdout.write(u"{} ({}) -> {}".format(membership.member, membership.type, next_type))

                    mandate = authorization_contribution(membership.member)

                    context = dataupdate_context(membership.member)
                    context['price'] = next_type.price
                    context['iban'] = mandate.iban if mandate else None
                    context['type'] = next_type

                    if not prev_prolong or (prev_prolong and not already_exists):
                        continuationmails.add_recipient(PersonRecipient(recipient=membership.member,
                                                                        context=context))

                    if commit:
                        l, created = Membership.objects.get_or_create(member=membership.member, type=next_type,
                                                                      year=new_year)

                        if payment_type:
                            if created:
                                b = Payment.objects.create(date=datetime.datetime(new_year, 7, 1),
                                                           membership=l,
                                                           payment_type=payment_type,
                                                           amount=next_type.price)
                                b.save()
                            else:
                                errorfile.write(smart_str(error_already_enrolled.format(membership.member,
                                                                                        membership.type)))

                        l.save()

                else:
                    if not prev_prolong and membership.type != ENIAC_MEMBERSHIP:
                        discontinuationmails_first.add_recipient(PersonRecipient(recipient=membership.member))
                        self.stdout.write(u"!! {} ({}) HAS NO VERIFIED MEMBERSHIP YET".format(membership.member,
                                                                                              membership.type))
                    elif not prev_prolong and membership.type == ENIAC_MEMBERSHIP:
                        discontinuationmails_eniac.add_recipient(PersonRecipient(recipient=membership.member))
                        self.stdout.write(u"!! {} ({}) CANCELLED BECAUSE OF ENIAC MEMBERSHIP".format(membership.member,
                                                                                                     membership.type))
                    else:
                        discontinuationmails_final.add_recipient(PersonRecipient(recipient=membership.member))
                        self.stdout.write(u"!! {} ({}) CANCELLED BECAUSE NOT VERIFIED IN TIME".format(membership.member,
                                                                                                      membership.type))

                    if membership.member.last_name_prefix:
                        last_name = '{} {}'.format(membership.member.last_name_prefix, membership.member.last_name)
                    else:
                        last_name = membership.member.last_name

                    discontinued_members_file.write(
                        smart_str(u"{}, {}, {}, {}\n".format(membership.member.first_name,
                                                             last_name,
                                                             membership.member.email_address,
                                                             membership.type.name))
                    )

        discontinued_members_file.close()
        errorfile.close()

        self.stdout.write(u"Sending mails...")

        if commit:
            continuationmails.send()
            discontinuationmails_first.send()
            discontinuationmails_final.send()
            discontinuationmails_eniac.send()

        self.stdout.write(u"Done")
