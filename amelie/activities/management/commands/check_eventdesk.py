import base64
import binascii
import html
import re
import email
from datetime import timedelta

import googleapiclient
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.datetime_safe import datetime
from django.utils.timezone import make_aware

from amelie.activities.models import EventDeskRegistrationMessage, Activity
from amelie.activities.utils import setlocale
from amelie.claudia.google import GoogleSuiteAPI

EVENT_REGISTERED_REGEX_NL = re.compile("Uw aanmelding voor bijeenkomst '(?P<meeting_name>.*)'")
EVENT_REGISTERED_REGEX_EN = re.compile("Your request for meeting '(?P<meeting_name>.*)'")
EVENT_ACCEPTED_REGEX = re.compile("Your request for meeting '(?P<meeting_name>.*)' is accepted")

EVENT_REGISTERED_CONTENT_REGEX_NL = re.compile("Beste (?P<requester>.*),(\r\n\r\n)? U ontvangt deze e-mail omdat u de "
                                            "bijeenkomst '(?P<meeting_name>.*)' op d\.?d\.? (?P<date_start>.*) t/m "
                                            "(?P<date_end>.*) voor locatie (?P<location>.*) bij ons aangemeld heeft.")
EVENT_REGISTERED_CONTENT_REGEX_EN = re.compile("Dear (?P<requester>.*),(\r\n\r\n)? You are receiving this e-mail because "
                                               "you registered the meeting '(?P<meeting_name>.*)' on the date "
                                               "(?P<date_start>.*) till (?P<date_end>.*) at (?P<location>.*) with us.")

EVENT_ACCEPTED_CONTENT_REGEX = re.compile("Dear (?P<requester>.*),(\r\n\r\n)? Your meeting '(?P<meeting_name>.*)' on the "
                                          "date (?P<date_start>.*) till (?P<date_end>.*) at (?P<location>.*) is "
                                          "accepted.")


def fuzzy_substring(needle, haystack):
    """
    Calculates the fuzzy match of needle in haystack, using a modified version of the Levenshtein distance
    algorithm. The function is modified from the levenshtein function in the bktree module by Adam Hupp
    """

    m, n = len(needle), len(haystack)

    # base cases
    if m == 1:
        return needle not in haystack
    if not n:
        return m

    row1 = [0] * (n + 1)
    for i in range(0, m):
        row2 = [i + 1]
        for j in range(0, n):
            cost = (needle[i] != haystack[j])

            row2.append(min(row1[j + 1] + 1,  # deletion
                            row2[j] + 1,  # insertion
                            row1[j] + cost)  # substitution
                        )
        row1 = row2
    return 1 - (min(row1) / len(needle))


class Command(BaseCommand):
    help = 'Check the event notices mailbox for new notices and processes them.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Checking event desk e-mail for new messages...'))
        # Set up Google API connection to GMail
        gmail_api = GoogleSuiteAPI.create_directory_service(
            user_email=settings.EVENT_DESK_NOTICES_EMAIL,
            api_name="gmail",
            api_version="v1",
            scopes=settings.CLAUDIA_GSUITE['SCOPES']['GMAIL_API']
        )

        num_processed = 0
        num_known = 0
        num_skipped = 0

        try:
            messages = gmail_api.users().messages().list(
                userId='me', q="in:inbox from:{}".format(settings.EVENT_DESK_FROM_EMAIL)
            ).execute()
            self.stderr.write("Around {} messages to process".format(messages['resultSizeEstimate']))
            if 'messages' not in messages:
                self.stderr.write("Nothing to do.")
                return

            for message in messages['messages']:
                message_id = message['id']
                try:
                    msg = EventDeskRegistrationMessage.objects.get(message_id=message_id)
                    content = ""
                    num_known += 1
                    # Message is already known, but was not previously archived.
                    # Archive the e-mail message, and add the label "Processed"
                    gmail_api.users().messages().modify(id=message_id, userId="me", body={
                        "removeLabelIds": ["UNREAD", "INBOX"],
                        "addLabelIds": [settings.EVENT_DESK_PROCESSED_LABEL_ID]
                    }).execute()
                except EventDeskRegistrationMessage.DoesNotExist:
                    # Retrieve the message from Google
                    msg_details = gmail_api.users().messages().get(id=message_id, userId='me', format='metadata').execute()
                    msg_raw = gmail_api.users().messages().get(id=message_id, userId='me', format='raw').execute()
                    self.stdout.write("New message {}.".format(message_id))

                    # Get the message subject
                    try:
                        subject = [x for x in msg_details['payload']['headers'] if x['name'] == "Subject"][0]['value']
                    except IndexError:
                        subject = "Unknown"

                    # Get the message timestamp
                    try:
                        timestamp = int(msg_details['internalDate']) // 1000
                        message_date = make_aware(datetime.fromtimestamp(timestamp))
                    except ValueError:
                        message_date = timezone.now()

                    # Get the message raw decoded to plain text
                    if msg_raw:
                        try:
                            msg_string = base64.urlsafe_b64decode(msg_raw['raw'].encode("UTF-8"))
                            mime_msg = email.message_from_string(msg_string.decode("UTF-8"))
                            content = None
                            for part in mime_msg.walk():
                                if part.get_content_type() == "text/plain":
                                    try:
                                        try:
                                            content = part.get_payload(decode=True).decode("utf-8")
                                        except UnicodeDecodeError:
                                            try:
                                                # UTF-8 not working, try Latin-1
                                                self.stderr.write(self.style.WARNING(
                                                    "Message is not encoded in UTF-8, trying Latin-1..."))
                                                content = part.get_payload(decode=True).decode("latin-1")
                                            except UnicodeDecodeError:
                                                # Latin-1 not working, try ASCII
                                                self.stderr.write(self.style.WARNING(
                                                    "Message is also not encoded in Latin-1, trying ASCII..."))
                                                content = part.get_payload(decode=True).decode("ASCII")
                                        if content is not None:
                                            break
                                    except UnicodeDecodeError:
                                        self.stderr.write(self.style.ERROR(
                                            "Message is not encoded in UTF-8, Latin-1 or ASCII, giving up..."))
                                elif content is None and part.get_content_type() == "text/html":
                                    import html2text
                                    try:
                                        try:
                                            text = part.get_payload(decode=True).decode("utf-8")
                                        except UnicodeDecodeError:
                                            try:
                                                # UTF-8 not working, try Latin-1
                                                self.stderr.write(self.style.WARNING(
                                                    "Message is not encoded in UTF-8, trying Latin-1..."))
                                                text = part.get_payload(decode=True).decode("latin-1")
                                            except UnicodeDecodeError:
                                                # Latin-1 not working, try ASCII
                                                self.stderr.write(self.style.WARNING(
                                                    "Message is not encoded in Latin-1, trying ASCII..."))
                                                text = part.get_payload(decode=True).decode("ASCII")
                                        content = html2text.html2text(text, bodywidth=0)
                                    except UnicodeDecodeError:
                                        self.stderr.write(self.style.ERROR(
                                            "Message is not encoded in UTF-8, Latin-1 or ASCII, giving up..."))
                        except binascii.Error as e:
                            content = html.unescape(msg_details['snippet'])
                            self.stderr.write(self.style.ERROR(
                                "Could not parse message {}'s Base64 ({}). "
                                "Trying to parse using the snippet below as a last resort:\n{}".format(
                                    message_id, e, content
                                ))
                            )
                    else:
                        content = html.unescape(msg_details['snippet'])
                        self.stderr.write(self.style.ERROR(
                            "Could not get message {}'s Base64. "
                            "Trying to parse using the snippet below as a last resort:\n{}".format(
                                message_id, content
                            ))
                        )

                    # See if this is one of the messages we are interested in.
                    match_registered = EVENT_REGISTERED_REGEX_NL.match(subject)
                    match_type = "nl"
                    if not match_registered:
                        match_registered = EVENT_REGISTERED_REGEX_EN.match(subject)
                        match_type = "en"
                    match_accepted = EVENT_ACCEPTED_REGEX.match(subject)

                    if match_accepted:
                        meeting_name = match_accepted.group("meeting_name")
                        match_content = EVENT_ACCEPTED_CONTENT_REGEX.search(content)
                        if match_content:
                            new_meeting_state = EventDeskRegistrationMessage.EventRegistrationStates.ACCEPTED
                            requester = match_content.group("requester")
                            location = match_content.group("location")
                            date_start_str = match_content.group("date_start")
                            date_end_str = match_content.group("date_end")
                            date_start = make_aware(datetime.strptime(date_start_str, "%d %B %Y %H:%M"))
                            date_end = make_aware(datetime.strptime(date_end_str, "%d %B %Y %H:%M"))

                        else:
                            self.stderr.write(self.style.ERROR(
                                "Could not find event info in acceptance message {} ({}), skipping...".format(
                                    message_id, subject
                                )
                            ))
                            num_skipped += 1
                            # Archive the e-mail message, and add the label "Error"
                            gmail_api.users().messages().modify(id=message_id, userId="me", body={
                                "removeLabelIds": ["UNREAD", "INBOX"],
                                "addLabelIds": [settings.EVENT_DESK_ERROR_LABEL_ID]
                            }).execute()
                            continue

                    elif match_registered:
                        meeting_name = match_registered.group("meeting_name")

                        match_content = EVENT_REGISTERED_CONTENT_REGEX_NL.search(content)
                        if not match_content:
                            match_content = EVENT_REGISTERED_CONTENT_REGEX_EN.search(content)

                        if match_content:
                            new_meeting_state = EventDeskRegistrationMessage.EventRegistrationStates.NEW
                            requester = match_content.group("requester")
                            location = match_content.group("location")
                            date_start_str = match_content.group("date_start")
                            date_end_str = match_content.group("date_end")

                            if match_type == "nl":
                                # Change the locale to NL, because the months in registration e-mails are in
                                # Dutch and strptime cannot parse them otherwise.
                                with setlocale(("nl_NL", "UTF-8")):
                                    date_start = make_aware(datetime.strptime(date_start_str, "%d %B %Y %H:%M"))
                                    date_end = make_aware(datetime.strptime(date_end_str, "%d %B %Y %H:%M"))
                            else:
                                # Use the default English locale
                                date_start = make_aware(datetime.strptime(date_start_str, "%d %B %Y %H:%M"))
                                date_end = make_aware(datetime.strptime(date_end_str, "%d %B %Y %H:%M"))

                        else:
                            self.stderr.write(self.style.ERROR(
                                "Could not find event info in registration message {} ({}), skipping...".format(
                                    message_id, subject
                                )
                            ))
                            num_skipped += 1
                            # Archive the e-mail message, and add the label "Error"
                            gmail_api.users().messages().modify(id=message_id, userId="me", body={
                                "removeLabelIds": ["UNREAD", "INBOX"],
                                "addLabelIds": [settings.EVENT_DESK_ERROR_LABEL_ID]
                            }).execute()
                            continue

                    else:
                        self.stderr.write(self.style.ERROR(
                            "Message {}'s subject ({}) does not match any patterns, ignoring.".format(message_id,
                                                                                                      subject)))
                        num_skipped += 1
                        # Archive the e-mail message, and add the label "Error"
                        gmail_api.users().messages().modify(id=message_id, userId="me", body={
                            "removeLabelIds": ["UNREAD", "INBOX"],
                            "addLabelIds": [settings.EVENT_DESK_ERROR_LABEL_ID]
                        }).execute()
                        continue

                    # Add margin to start and end times to help in the search for the matching activity
                    date_start = date_start - timedelta(hours=1)
                    date_end = date_end + timedelta(hours=1)

                    # Find activity based on time and meeting name
                    candidates = Activity.objects.filter(begin__gt=date_start, end__lte=date_end).order_by('begin')
                    matching_activity = None
                    match_ratio = -1

                    # If there is only one candidate, match the event to that activity
                    if len(candidates) > 0:
                        # Calculate the best possible match based on the name of the meeting and the activity
                        maxratio = 0
                        best_match = None
                        for act in candidates:

                            ratio_nl = fuzzy_substring(meeting_name.lower(), act.summary_nl.lower())
                            ratio_en = fuzzy_substring(meeting_name.lower(), act.summary_en.lower())
                            ratio = max(ratio_nl, ratio_en)
                            if ratio > maxratio:
                                maxratio = ratio
                                best_match = act

                        matching_activity = best_match
                        match_ratio = maxratio

                    # Create registration
                    self.stdout.write(self.style.SUCCESS(
                        "Registration {} {} for activity {} (certainty {:.2f}%), requested by {} under name {} on {}".format(
                            message_id, new_meeting_state, matching_activity, match_ratio * 100, requester,
                            meeting_name, message_date
                        )))
                    reg_msg = EventDeskRegistrationMessage.objects.create(
                        message_id=message_id,
                        message_date=message_date,
                        activity=matching_activity,
                        state=new_meeting_state,
                        requester=requester,
                        event_name=meeting_name,
                        event_start=date_start_str,
                        event_end=date_end_str,
                        event_location=location,
                        match_ratio=match_ratio if matching_activity else None
                    )

                    # Archive the e-mail message, and add the label "Processed"
                    gmail_api.users().messages().modify(id=message_id, userId="me", body={
                        "removeLabelIds": ["UNREAD", "INBOX"],
                        "addLabelIds": [settings.EVENT_DESK_PROCESSED_LABEL_ID]
                    }).execute()

                    num_processed += 1
        except googleapiclient.errors.HttpError as e:
            self.stderr.write(self.style.ERROR("Could not retrieve messages for user {} - Message: {}".format(
                settings.EVENT_DESK_NOTICES_EMAIL, e
            )))

        self.stdout.write(self.style.SUCCESS('Result: {} new states saved, {} already known, and {} skipped due '
                                             'to parse errors.'.format(num_processed, num_known, num_skipped)))
        self.stdout.write(self.style.SUCCESS('Event desk check completed.'))
