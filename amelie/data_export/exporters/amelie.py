import os

import json
from django.utils.translation import gettext_lazy as _
from oauth2_provider.models import Application, AccessToken, Grant
from zipfile import ZipFile

from social_django.models import UserSocialAuth

from amelie.claudia.models import Mapping, Timeline, Event as ClaudiaEvent
from amelie.data_export.exporters.exporter import DataExporter
from amelie.personal_tab.models import ReversalTransaction, DebtCollectionTransaction, CustomTransaction, \
    CookieCornerTransaction, ContributionTransaction, AlexiaTransaction, ActivityTransaction


class AmelieDataExporter(DataExporter):
    def export_data(self):
        self.log.debug("Exporting amelie data for {} to {}".format(self.data_export.person, self.filename))

        with ZipFile(self.filename, 'w') as export_file:
            export_claudia, files_claudia = self.export_claudia()
            export_file.writestr(
                'account.json',
                json.dumps(export_claudia, indent=2, sort_keys=True)
            )
            for file in files_claudia:
                filename = os.path.basename(file)
                export_file.write(file, arcname=os.path.join("account_files", filename))

            export_calendar, files_calendar = self.export_calendar()
            export_file.writestr(
                'enrollments.json',
                json.dumps(export_calendar, indent=2, sort_keys=True)
            )
            for file in files_calendar:
                filename = os.path.basename(file)
                export_file.write(file, arcname=os.path.join("enrollments_files", filename))

            export_room_duty, files_room_duty = self.export_roomduty()
            export_file.writestr(
                'room_duty.json',
                json.dumps(export_room_duty, indent=2, sort_keys=True)
            )
            for file in files_room_duty:
                filename = os.path.basename(file)
                export_file.write(file, arcname=os.path.join("room_duty_files", filename))

            export_member, files_member = self.export_member()
            export_file.writestr(
                'member.json',
                json.dumps(export_member, indent=2, sort_keys=True)
            )
            for file in files_member:
                filename = os.path.basename(file)
                export_file.write(file, arcname=os.path.join("member_files", filename))

            export_news, files_news = self.export_news()
            export_file.writestr(
                'news.json',
                json.dumps(export_news, indent=2, sort_keys=True)
            )
            for file in files_news:
                filename = os.path.basename(file)
                export_file.write(file, arcname=os.path.join("news_files", filename))

            export_oauth, files_oauth = self.export_oauth()
            export_file.writestr(
                'oauth.json',
                json.dumps(export_oauth, indent=2, sort_keys=True)
            )
            for file in files_oauth:
                filename = os.path.basename(file)
                export_file.write(file, arcname=os.path.join("oauth_files", filename))

            export_education, files_education = self.export_education()
            export_file.writestr(
                'education.json',
                json.dumps(export_education, indent=2, sort_keys=True)
            )
            for file in files_education:
                filename = os.path.basename(file)
                export_file.write(file, arcname=os.path.join("education_files", filename))

            export_personal_tab, files_personal_tab = self.export_personal_tab()
            export_file.writestr(
                'personal_tab.json',
                json.dumps(export_personal_tab, indent=2, sort_keys=True)
            )
            for file in files_personal_tab:
                filename = os.path.basename(file)
                export_file.write(file, arcname=os.path.join("personal_tab_files", filename))

        return self.filename

    def export_claudia(self):
        claudia_data = {}

        # - Mapping that belongs to the person
        claudia_mapping = Mapping.find(self.data_export.person)
        if claudia_mapping:
            # - Groups and aliases that these Mappings belong to
            claudia_data['groups'] = [str(x) for x in claudia_mapping.groups('all')]
            claudia_data['aliases'] = [str(x) for x in claudia_mapping.aliases()]

            # - Timeline entries that belong to these Mappings
            person_timeline_entries = Timeline.objects.filter(mapping=claudia_mapping)
            claudia_data['timeline'] = [{
                'datetime': str(timeline.datetime),
                'name': str(timeline.name),
                'type': str(timeline.type),
                'description': str(timeline.description)
            } for timeline in person_timeline_entries]

            # - Events that are scheduled for these Mappings
            person_events = ClaudiaEvent.objects.filter(mapping=claudia_mapping)
            claudia_data['scheduled_events'] = [{
                'type': str(event.type),
                'to_execute_on': str(event.execute),
            } for event in person_events]

        return claudia_data, []

    def export_calendar(self):
        calendar_data = {'enrollments': []}

        # - Events for which the person enrolled and the options they gave for it.
        person_enrollments = self.data_export.person.participation_set.all()
        for enrollment in person_enrollments:
            enrollment_data = {
                'remark': str(enrollment.remark),
                'payment_method': str(enrollment.get_payment_method_display()),
                'enrollment_time': str(enrollment.added_on),
                'enrollment_options': [],
            }
            if hasattr(enrollment, 'event'):
                enrollment_data['event'] = "{} ({} - {})".format(enrollment.event.summary, enrollment.event.begin,
                                                                 enrollment.event.end)
            else:
                enrollment_data['event'] = _('deleted activity')

            for enrollment_option_answer in enrollment.enrollmentoptionanswer_set.all():
                enrollment_data['enrollment_options'].append({
                    'name': str(enrollment_option_answer.enrollmentoption.title),
                    'answer': str(enrollment_option_answer.display_answer),
                    'price': str(enrollment_option_answer.get_price_extra()),
                })

            calendar_data['enrollments'].append(enrollment_data)

        return calendar_data, []

    def export_roomduty(self):
        person_room_duty_pools = self.data_export.person.room_duty_pools.all()
        person_room_duty_duties = self.data_export.person.room_duties.all()

        return {
            'pools': [str(pool.name) for pool in person_room_duty_pools],
            'room_duties': [{
                'schedule': str(duty.table),
                'begin': str(duty.begin),
                'end': str(duty.end),
            } for duty in person_room_duty_duties]
        }, []

    def export_member(self):
        person = self.data_export.person
        member_data = {
            'first_name': str(person.first_name),
            'last_name_prefix': str(person.last_name_prefix),
            'last_name': str(person.last_name),
            'initials': str(person.initials),
            'slug': str(person.slug),
            'notes': str(person.notes),
            'gender': str(person.get_gender_display()),
            'preferred_language': str(person.get_preferred_language_display()),
            'international_member': str(person.international_member),
            'date_of_birth': str(person.date_of_birth),
            'address': str(person.address),
            'postal_code': str(person.postal_code),
            'city': str(person.city),
            'country': str(person.country),
            'email_address': str(person.email_address if person.email_address else ""),
            'telephone_number': str(person.telephone),
            'address_parents': str(person.address_parents),
            'postal_code_parents': str(person.postal_code_parents),
            'city_parents': str(person.city_parents),
            'country_parents': str(person.country_parents),
            'email_address_parents': str(person.email_address_parents),
            'can_use_parents_address': person.can_use_parents_address,
            'account_name': str(person.account_name),
            'shell': str(person.get_shell_display()),
            'webmaster': person.webmaster,
            'picture': None,
            'preferences': [],
            'user': None,
            'dogroup_parenthoods': [],
            'student': None,
            'employee': None,
            'memberships': [],
            'functions': [],
        }
        member_files = []

        if person.picture:
            member_data['picture'] = os.path.join("member_files", os.path.basename(person.picture.path))
            member_files.append(person.picture.path)

        member_data['preferences'] = [str(preference) for preference in person.preferences.all()]

        if hasattr(person, 'user'):
            member_data['user'] = {
                'username': str(person.user.username),
                'first_name': str(person.user.first_name),
                'last_name': str(person.user.last_name),
                'email': str(person.user.email),
                'is_staff': person.user.is_staff,
                'is_active': person.user.is_active,
                'is_superuser': person.user.is_superuser,
                'date_joined': str(person.user.date_joined),
                'last_login': str(person.user.last_login),
                'groups': [group.name for group in person.user.groups.all()],
                'permissions': [str(permission) for permission in person.user.user_permissions.all()],
                'profile': str(person.user.profile)
            }

        member_data['dogroup_parenthoods'] = [str(dogroup) for dogroup in person.dogroupgeneration_set.all()]

        if person.is_student():
            member_data['student'] = {
                'number': person.student.student_number(),
                'enrolled_in_primary_study': person.student.enrolled_in_primary_study(),
                'study_periods': [{
                    'study': str(study_period.study),
                    'begin': str(study_period.begin),
                    'end': str(study_period.end) if study_period.end else None,
                    'graduated': study_period.graduated,
                    'do_group': str(study_period.dogroup) if study_period.dogroup else None,
                } for study_period in person.student.studyperiod_set.all()]
            }

        if person.is_employee():
            member_data['employee'] = {
                'number': person.employee.employee_number(),
                'end_date': str(person.employee.end) if person.employee.end else None,
            }

        person_memberships = []
        for membership in person.membership_set.all():
            membership_data = {
                'membership_type': str(membership.type),
                'year': membership.year,
                'ended_prematurely_on': str(membership.ended) if membership.ended else None,
                'payment': None,
            }
            if hasattr(membership, 'payment') and membership.payment:
                membership_data['payment'] = {
                    'date': str(membership.payment.date),
                    'payment_type': str(membership.payment.payment_type),
                    'price': str(membership.payment.amount)
                }
            person_memberships.append(membership_data)
        member_data['memberships'] = person_memberships

        person_functions = []
        for func in person.function_set.all():
            function_data = {
                'committee': str(func.committee),
                'function': str(func.function),
                'start_date': str(func.begin),
                'end_date': str(func.end) if func.end else None,
                'note': str(func.note),
            }
            person_functions.append(function_data)
        member_data['functions'] = person_functions

        return member_data, member_files

    def export_news(self):
        return {
            'news_posts': [{
                'publication_date': str(post.publication_date),
                'title_nl': str(post.title_nl),
                'title_en': str(post.title_en),
                'slug': str(post.slug),
                'introduction_nl': str(post.introduction_nl),
                'introduction_en': str(post.introduction_en),
                'content_nl': str(post.content_nl),
                'content_en': str(post.content_en),
            } for post in self.data_export.person.newsitem_set.all()]
        }, []

    def export_oauth(self):
        person = self.data_export.person

        oauth_data = {}

        if hasattr(person, 'user'):
            oauth_data['oauth'] = {
                'registered_oauth_applications': [
                    str(application.name) for application in Application.objects.filter(user=person.user)
                ],
                'access_tokens': [{
                    'application': str(token.application),
                    'expiry_date': str(token.expires),
                    'scopes': str(token.scope)
                } for token in AccessToken.objects.filter(user=person.user)],
                'grants': [{
                    'code': str(grant.code),
                    'application': str(grant.application),
                    'expiry_date': str(grant.expires),
                    'scopes': str(grant.scope),
                } for grant in Grant.objects.filter(user=person.user)],
                'authentication_providers': [{
                    'provider': auth.provider,
                    'uid': auth.uid,
                    'extra_data': auth.extra_data,
                } for auth in UserSocialAuth.objects.filter(user=person.user)],
            }

        return oauth_data, []

    def export_education(self):
        return {
            'own_complaints': [{
                'published_date': str(complaint.published),
                'subject': str(complaint.subject),
                'summary': str(complaint.summary),
                'comment': str(complaint.comment),
                'public': complaint.public,
                'progress': complaint.progress,
                'anonymous': complaint.anonymous,
                'completed': complaint.completed,
                'course': str(complaint.course) if complaint.course else None,
                'part': str(complaint.part) if complaint.part else None,
                'year': complaint.year if complaint.year else None,
                'period': str(complaint.period) if complaint.period else None,
            } for complaint in self.data_export.person.complaint_set.all()],
            'also_affects_me': [{
                'subject': str(complaint.subject),
                'summary': str(complaint.summary),
                'course': str(complaint.course) if complaint.course else None,
                'part': str(complaint.part) if complaint.part else None,
                'year': complaint.year if complaint.year else None,
                'period': str(complaint.period) if complaint.period else None,
            } for complaint in self.data_export.person.personen.all()],
            'complaint_comments': [{
                'published_date': str(comment.published),
                'public': comment.public,
                'complaint': {
                    'subject': str(comment.complaint.subject),
                    'summary': str(comment.complaint.summary),
                    'course': str(comment.complaint.course) if comment.complaint.course else None,
                    'part': str(comment.complaint.part) if comment.complaint.part else None,
                    'year': comment.complaint.year if comment.complaint.year else None,
                    'period': str(comment.complaint.period) if comment.complaint.period else None,
                },
                'comment': str(comment.comment),
            } for comment in self.data_export.person.complaintcomment_set.all()],
            'competition_votes': [str(vote.competition) for vote in self.data_export.person.vote_set.all()],
        }, []

    def export_personal_tab(self):
        person = self.data_export.person
        personal_tab_data = {
            'discount_credits': [{
                'discount_period': str(credit.discount_period),
                'date': str(credit.date),
                'price': str(credit.price),
                'description': str(credit.description),
                'discount': str(credit.discount) if credit.discount else None,
                'added_on': str(credit.added_on),
            } for credit in person.discountcredit_set.all()],
            'transactions': {
                'activty_transactions': [{
                    'date': str(transaction.date),
                    'price': str(transaction.price),
                    'description': str(transaction.description),
                    'discount': str(transaction.discount) if transaction.discount else None,
                    'debt_collection': str(transaction.debt_collection) if transaction.debt_collection else None,
                    'added_on': str(transaction.added_on),
                    'event': str(transaction.event),
                    'participation': str(transaction.participation),
                    'has_enrollment_options': transaction.with_enrollment_options,
                } for transaction in ActivityTransaction.objects.filter(person=person)],
                'alexia_transactions': [{
                    'date': str(transaction.date),
                    'price': str(transaction.price),
                    'description': str(transaction.description),
                    'discount': str(transaction.discount) if transaction.discount else None,
                    'debt_collection': str(transaction.debt_collection) if transaction.debt_collection else None,
                    'added_on': str(transaction.added_on),
                    'alexia_id': transaction.transaction_id,
                } for transaction in AlexiaTransaction.objects.filter(person=person)],
                'contribution_transactions': [{
                    'date': str(transaction.date),
                    'price': str(transaction.price),
                    'description': str(transaction.description),
                    'discount': str(transaction.discount) if transaction.discount else None,
                    'debt_collection': str(transaction.debt_collection) if transaction.debt_collection else None,
                    'added_on': str(transaction.added_on),
                    'membership': str(transaction.membership)
                } for transaction in ContributionTransaction.objects.filter(person=person)],
                'cookie_corner_transactions': [{
                    'date': str(transaction.date),
                    'price': str(transaction.price),
                    'description': str(transaction.description),
                    'discount': str(transaction.discount) if transaction.discount else None,
                    'debt_collection': str(transaction.debt_collection) if transaction.debt_collection else None,
                    'added_on': str(transaction.added_on),
                    'article': str(transaction.article),
                    'amount': str(transaction.amount),
                } for transaction in CookieCornerTransaction.objects.filter(person=person)],
                'custom_transactions': [{
                    'date': str(transaction.date),
                    'price': str(transaction.price),
                    'description': str(transaction.description),
                    'discount': str(transaction.discount) if transaction.discount else None,
                    'debt_collection': str(transaction.debt_collection) if transaction.debt_collection else None,
                    'added_on': str(transaction.added_on),
                } for transaction in CustomTransaction.objects.filter(person=person)],
                'debt_collection_transactions': [{
                    'date': str(transaction.date),
                    'price': str(transaction.price),
                    'description': str(transaction.description),
                    'discount': str(transaction.discount) if transaction.discount else None,
                    'debt_collection': str(transaction.debt_collection) if transaction.debt_collection else None,
                    'added_on': str(transaction.added_on),
                } for transaction in DebtCollectionTransaction.objects.filter(person=person)],
                'reversal_transactions': [{
                    'date': str(transaction.date),
                    'price': str(transaction.price),
                    'description': str(transaction.description),
                    'discount': str(transaction.discount) if transaction.discount else None,
                    'debt_collection': str(transaction.debt_collection) if transaction.debt_collection else None,
                    'added_on': str(transaction.added_on),
                    'reversal': str(transaction.reversal),
                } for transaction in ReversalTransaction.objects.filter(person=person)],
            },
            'rfid_cards': [{
                'code': str(card),
                'active': card.active,
                'last_used': str(card.last_used),
                'created': str(card.created),
            } for card in person.rfidcard_set.all()],
            'authorizations': [{
                'type': str(authorization.authorization_type),
                'iban': str(authorization.iban),
                'bic': str(authorization.bic),
                'account_holder': str(authorization.account_holder_name),
                'start_date': str(authorization.start_date),
                'end_date': str(authorization.end_date) if authorization.end_date else None,
                'is_signed': authorization.is_signed,
                'reference': str(authorization.authorization_reference()),
                'amendments': [{
                    'date': str(amendment.date),
                    'previous_iban': str(amendment.previous_iban),
                    'previous_bic': str(amendment.previous_bic),
                    'other_bank': amendment.other_bank,
                    'reason': str(amendment.reason),
                } for amendment in authorization.amendments.all()],
                'debt_collection_instructions': [{
                    'reference': str(instruction.debt_collection_reference()),
                    'batch': str(instruction.batch),
                    'end_to_end_id': str(instruction.end_to_end_id),
                    'description': str(instruction.description),
                    'amount': str(instruction.amount),
                    'amendment': {
                        'date': str(instruction.amendment.date),
                        'previous_iban': str(instruction.amendment.previous_iban),
                        'previous_bic': str(instruction.amendment.previous_bic),
                        'other_bank': instruction.amendment.other_bank,
                        'reason': str(instruction.amendment.reason),
                    } if instruction.amendment else None,
                    'reversal': {
                        'date': str(instruction.reversal.date),
                        'pre_settlement': instruction.reversal.pre_settlement,
                        'reason': str(instruction.reversal.get_reason_display()),
                    } if hasattr(instruction, 'reversal') else None,
                } for instruction in authorization.instructions.all()],
            } for authorization in person.authorization_set.all()],
        }

        return personal_tab_data, []
