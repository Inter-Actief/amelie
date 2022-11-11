import datetime
import getpass
import io
import os
import random
import uuid
from datetime import timedelta

from PIL import ImageColor, ImageFont, Image, ImageDraw, ImageOps
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import DefaultStorage
from model_bakery import baker
from django.utils import timezone
from model_bakery.recipe import Recipe
from oauth2_provider.models import Application

from amelie.files.models import Attachment
from amelie.members.models import MembershipType, Study, CommitteeCategory, Committee, Membership
from amelie.personal_tab.models import AuthorizationType
from amelie.tools.logic import current_association_year
from amelie.tools.management.base import DevelopmentOnlyCommand
from django.contrib.auth import get_user_model

from django.db.migrations.executor import MigrationExecutor
from django.db import connections, DEFAULT_DB_ALIAS

PERSON_MODEL_STRING = 'members.Person'
ACTIVITY_MODEL_STRING = 'activities.Activity'


###
# Generator functions for specific items that ModelBakery does not have its own generators for
###
def gen_date_before_today():
    min_date = datetime.date.today() - datetime.timedelta(365 * 5)
    max_date = datetime.date.today()
    diff = max_date - min_date
    days = random.randint(0, diff.days)
    date = min_date + datetime.timedelta(days=days)
    return date


def gen_datetime_between(min_date, max_date):
    def gen_datetime_between_dates():
        diff = max_date - min_date
        seconds = random.randint(0, diff.days * 3600 * 24 + diff.seconds)
        return min_date + datetime.timedelta(seconds=seconds)
    return gen_datetime_between_dates


def gen_integer_between(min_int, max_int):
    return lambda: random.randint(min_int, max_int)


def get_color(name):
    return ImageColor.getrgb(name)


def get_placeholder_image(width, height, fg_color=get_color('black'), bg_color=get_color('grey'), text=None,
                          font='Verdana.ttf', fontsize=42, encoding='unic', mode='RGBA', fmt='PNG'):
    """Little spin-off from https://github.com/Visgean/python-placeholder
    that not saves an image and instead returns it."""
    size = (width, height)
    text = text if text else '{0}x{1}'.format(width, height)

    try:
        font = ImageFont.truetype(font, size=fontsize, encoding=encoding)
    except IOError:
        font = ImageFont.load_default()

    result_img = Image.new(mode, size, bg_color)

    text_size = font.getsize(text)
    text_img = Image.new("RGBA", size, bg_color)

    # position for the text:
    left = size[0] / 2 - text_size[0] / 2
    top = size[1] / 2 - text_size[1] / 2

    drawing = ImageDraw.Draw(text_img)
    drawing.text((left, top),
                 text,
                 font=font,
                 fill=fg_color)

    txt_img = ImageOps.fit(text_img, size, method=Image.BICUBIC, centering=(0.5, 0.5))

    result_img.paste(txt_img)
    file_obj = io.BytesIO()
    txt_img.save(file_obj, fmt)

    return file_obj.getvalue()


def gen_image_by_dimensions(width, height):
    """
    Generates a valid placeholder image and saves it to the ``settings.MEDIA_ROOT``
    The returned filename is relative to ``MEDIA_ROOT``.
    """

    def gen_image_with_dimensions():
        storage = DefaultStorage()
        # Ensure that _dummydata folder exists.
        _path = '_dummydata'
        suffix = str(uuid.uuid4())
        filename = '{width}x{height}-{suffix}.png'.format(width=width, height=height, suffix=suffix)
        path = os.path.join(_path, filename)
        storage.save(path, ContentFile(get_placeholder_image(width, height)))
        return ContentFile(get_placeholder_image(width, height), name=path)
    return gen_image_with_dimensions


def gen_coinflip():
    return random.choice([True, False])


def is_database_synchronized(database):
    connection = connections[database]
    connection.prepare_database()
    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()
    return not executor.migration_plan(targets)


###
# The actual command
###
class Command(DevelopmentOnlyCommand):
    help = 'Generate dummy data into a (preferrably empty) database to be used in development purposes.'

    changes_database = True

    def handle(self, *args, **options):
        # Check for OK
        if not super(Command, self).handle(*args, **options):
            return

        if not is_database_synchronized(DEFAULT_DB_ALIAS):
            self.stdout.write("Your database does not have all migrations applied! "
                              "Run `python manage.py migrate` first!")
            return

        # Print warning
        self.stdout.write('This command might take a while (1-5 min).\n')

        ##
        # First check if or create the model instances are created that are needed for the site to work properly.
        ##
        # Get the user model that is used by Django
        User = get_user_model()

        # Ask for superuser details
        enter_details = None
        while enter_details is None:
            enter_details_q = input("Do you want to create a superuser account? (Y/n)")
            enter_details_y = enter_details_q.lower() in ["y", "yes", ""]
            enter_details_n = enter_details_q.lower() in ["n", "no"]
            enter_details = True if enter_details_y else (False if enter_details_n else None)

        admin_username = None
        admin_firstname = None
        admin_lastname = None
        admin_email = None
        admin_password = None
        if enter_details:
            admin_done = False
            while not admin_done:
                while not admin_username:
                    username_q = input("Please enter a username: ")
                    if username_q:
                        admin_username = username_q

                while not admin_password:
                    password_1_q = getpass.getpass("Please enter a password: ")
                    password_2_q = getpass.getpass("Please enter the password again: ")
                    if password_1_q and password_2_q and password_1_q == password_2_q:
                        admin_password = password_1_q
                    else:
                        self.stdout.write("Passwords empty or did not match, please retry.")

                while not admin_firstname:
                    firstname_q = input("Please enter a first name: ")
                    if firstname_q:
                        admin_firstname = firstname_q

                while not admin_lastname:
                    lastname_q = input("Please enter a last name: ")
                    if lastname_q:
                        admin_lastname = lastname_q

                while not admin_email:
                    email_q = input("Please enter an e-mail address: ")
                    if email_q:
                        admin_email = email_q

                if admin_username and admin_email and admin_password:
                    admin_done = True

            self.stdout.write("A superuser account named '{}' will be created.".format(admin_username))
        else:
            self.stdout.write("A superuser account will be created for you if it does not exist yet.")

        # At least one (super)user should exist, which is linked to a Person object and has a Profile.
        if enter_details or len(User.objects.all()) == 0:
            if not enter_details:
                admin_username = "admin"
                admin_email = "admin@example.com"
                admin_password = str(uuid.uuid4()).replace("-", "")
                admin_firstname = "Admin"
                admin_lastname = "Admin"
            user = User.objects.create_superuser(admin_username, admin_email, admin_password,
                                                 first_name=admin_firstname, last_name=admin_lastname)
            person = baker.make(PERSON_MODEL_STRING)
            person.user = user
            person.email_address = admin_email
            person.first_name = admin_firstname
            person.last_name = admin_lastname
            person.save()
            self.stdout.write("Created a superuser with username '{}'.".format(admin_username))
            if not enter_details:
                self.stdout.write("The password for this account is '{}'".format(admin_password))
        else:
            self.stdout.write("A superuser account already exists. Assuming that it is setup correctly.")
            person = None

        self.stdout.write("Creating model instances that the website requires to function...")

        # MembershipTypes "Primary yearlong", "Studylong (first year)", "Secondary yearlong" and "Employee yearlong"
        if not MembershipType.objects.filter(name_en="Primary yearlong").exists():
            MembershipType.objects.create(name_nl="Primair jaarlid", name_en="Primary yearlong", price=2)
        if not MembershipType.objects.filter(name_en="Studylong (first year)").exists():
            MembershipType.objects.create(name_nl="Studielang (eerste jaar)", name_en="Studylong (first year)", price=5)
        if not MembershipType.objects.filter(name_en="Secondary yearlong").exists():
            MembershipType.objects.create(name_nl="Secundair jaarlid", name_en="Secondary yearlong", price=1)
        if not MembershipType.objects.filter(name_en="Employee yearlong").exists():
            MembershipType.objects.create(name_nl="Medewerker jaarlid", name_en="Employee yearlong", price=2)

        # Add an active membership for the created superuser (if one was created)
        if person is not None:
            mst = MembershipType.objects.get(name_en="Primary yearlong")
            Membership.objects.create(member=person, type=mst, year=current_association_year())

        # At least one active primary study should exist
        if not Study.objects.filter(primary_study=True, active=True).exists():
            Study.objects.create(name_nl="Informatica", name_en="Computer Science", abbreviation="INF",
                                 type="BSc", length=3, primary_study=True, active=True)

        # At least one CommitteeCategory should exist
        if not CommitteeCategory.objects.exists():
            CommitteeCategory.objects.create(name="General")
            CommitteeCategory.objects.create(name=settings.POOL_CATEGORY)

        # Committees "Beheer", "WWW", "MediaCie", "Vivat" and "OnderwijsCommissie" should exist
        if not Committee.objects.filter(abbreviation=settings.SYSADMINS_ABBR, abolished__isnull=True).exists():
            Committee.objects.create(name=settings.SYSADMINS_ABBR, abbreviation=settings.SYSADMINS_ABBR,
                                     information_nl=settings.SYSADMINS_ABBR, information_en=settings.SYSADMINS_ABBR)
        if not Committee.objects.filter(abbreviation="WWW", abolished__isnull=True).exists():
            Committee.objects.create(name="WWW", abbreviation="WWW",
                                     information_nl="WWW", information_en="WWW")
        if not Committee.objects.filter(abbreviation="MediaCie", abolished__isnull=True).exists():
            Committee.objects.create(name="MedIA Committee", abbreviation="MediaCie",
                                     information_nl="MedIA-commissie", information_en="MedIA committee")
        if not Committee.objects.filter(abbreviation="Vivat", abolished__isnull=True).exists():
            Committee.objects.create(name="Vivat", abbreviation="Vivat",
                                     information_nl="Vivat", information_en="Vivat")
        if not Committee.objects.filter(abbreviation=settings.EDUCATION_COMMITTEE_ABBR,
                                        abolished__isnull=True).exists():
            Committee.objects.create(name=settings.EDUCATION_COMMITTEE_ABBR,
                                     abbreviation=settings.EDUCATION_COMMITTEE_ABBR,
                                     information_nl=settings.EDUCATION_COMMITTEE_ABBR,
                                     information_en=settings.EDUCATION_COMMITTEE_ABBR)

        # The Personal Tab default settings require that at least 3 discount periods exist
        baker.make('personal_tab.DiscountPeriod', _quantity=3)

        # The SEPA authorizations require that an AuthorizationType exists for Contribution and for other stuff
        if not AuthorizationType.objects.filter(active=True, contribution=True).exists():
            AuthorizationType.objects.create(name_nl="Contributie", name_en="Contribution",
                                             text_nl="Contributie", text_en="Contribution",
                                             active=True, contribution=True)
        if not AuthorizationType.objects.filter(active=True, consumptions=True,
                                                activities=True, other_payments=True).exists():
            AuthorizationType.objects.create(name_nl="Overig", name_en="Other", text_nl="Overig", text_en="Other",
                                             active=True, consumptions=True, activities=True, other_payments=True)

        ##
        # Create random models from the Members module
        ##
        self.stdout.write("Creating random models from the Members module...")
        # 5 Faculties
        self.stdout.write("- 5 faculties...")
        baker.make('members.Faculty', _quantity=5)
        # 5 Departments
        self.stdout.write("- 5 departments...")
        baker.make('members.Department', _quantity=5)
        # 10 Studies
        self.stdout.write("- 10 studies...")
        baker.make('members.Study', _quantity=10)
        # 10 Do-groups
        self.stdout.write("- 10 do-groups...")
        baker.make('members.Dogroup', _quantity=10)
        # 40 Do-group generations
        self.stdout.write("- 40 do-group generations...")
        baker.make('members.DogroupGeneration', _quantity=40)
        # 2 PreferenceCategories
        self.stdout.write("- 2 preference categories...")
        baker.make('members.PreferenceCategory', _quantity=2)
        # 10 Preferences
        self.stdout.write("- 10 preferences...")
        baker.make('members.Preference', _quantity=10)
        # 2 PaymentTypes
        self.stdout.write("- 2 payment types...")
        baker.make('members.PaymentType', _quantity=2)
        # 80 Persons with Memberships and Students and StudyPeriods
        self.stdout.write("- 80 persons with memberships, students and study periods...")
        students = baker.make(PERSON_MODEL_STRING, user=None, _quantity=80)
        for student in students:
            baker.make('members.Membership',
                       member=student,
                       year=current_association_year(),
                       ended=None)
            s = baker.make('members.Student', person=student)
            baker.make('members.StudyPeriod', student=s, begin=gen_date_before_today)
        # 10 Persons with expired memberships (old members) and Students and StudyPeriods
        self.stdout.write("- 10 persons with expired memberships (old members), students and study periods...")
        students = baker.make(PERSON_MODEL_STRING, user=None, _quantity=10)
        for student in students:
            baker.make('members.Membership',
                       member=student,
                       year=current_association_year()-1,
                       ended=None)
            s = baker.make('members.Student', person=student)
            baker.make('members.StudyPeriod', student=s, begin=gen_date_before_today)
        # 20 Persons with Memberships and Employees
        self.stdout.write("- 20 persons with memberships and employees...")
        employees = baker.make(PERSON_MODEL_STRING, user=None, _quantity=20)
        for employee in employees:
            baker.make('members.Membership',
                       member=employee,
                       year=current_association_year(),
                       ended=None)
            baker.make('members.Employee', person=employee, end=None)
        # 50 Payments (half of students and half of employees)
        self.stdout.write("- 50 payments for half of the students and half of the employees...")
        random.shuffle(students)
        half_students = students[:40]
        random.shuffle(employees)
        half_employees = employees[:10]
        for person in half_students + half_employees:
            baker.make('members.Payment',
                       membership=person.membership_set.first(),
                       amount=person.membership_set.first().type.price)
        # 2 CommitteeCategories
        self.stdout.write("- 2 committee categories...")
        baker.make('members.CommitteeCategory', _quantity=2)
        # 20 Committees
        self.stdout.write("- 20 committees...")
        baker.make('members.Committee', _quantity=20)
        # 100 Functions
        self.stdout.write("- 100 committee functions...")
        baker.make('members.Function', _quantity=100)

        ##
        # Create some random activities and enrollments
        ##
        self.stdout.write("Creating random models from the Activities module...")
        # 20 Activities that might have enrollments between three weeks ago and three weeks from now
        self.stdout.write("- 20 activities with (possibly) enrollments between 3 weeks ago and 3 weeks from now...")
        baker.make(ACTIVITY_MODEL_STRING,
                   begin=gen_datetime_between(
                       min_date=timezone.now() - timedelta(weeks=3),
                       max_date=timezone.now() + timedelta(weeks=3)
                   ),
                   end=gen_datetime_between(
                       min_date=timezone.now() - timedelta(weeks=3),
                       max_date=timezone.now() + timedelta(weeks=3)
                   ),
                   _quantity=20)
        # 20 activities with unlimited enrollments between three weeks ago and three weeks from now,
        # with between 0 and 10 enrollments
        self.stdout.write("- 20 activities with unlimited enrollments and 0 to 10 enrollments, "
                          "between 3 weeks ago and 3 weeks from now...")
        as_unlimited_enroll = baker.make(ACTIVITY_MODEL_STRING,
                                         begin=gen_datetime_between(
                                             min_date=timezone.now() - timedelta(weeks=3),
                                             max_date=timezone.now() + timedelta(weeks=3)
                                         ),
                                         end=gen_datetime_between(
                                             min_date=timezone.now() - timedelta(weeks=3),
                                             max_date=timezone.now() + timedelta(weeks=3)
                                         ),
                                         maximum=None, enrollment=True,
                                         enrollment_begin=gen_datetime_between(
                                             min_date=timezone.now() - timedelta(weeks=3),
                                             max_date=timezone.now() + timedelta(weeks=3)
                                         ),
                                         enrollment_end=gen_datetime_between(
                                             min_date=timezone.now() - timedelta(weeks=3),
                                             max_date=timezone.now() + timedelta(weeks=3)
                                         ),
                                         _quantity=20)
        for activity in as_unlimited_enroll:
            num_enrollments = random.randint(0, 10)
            if num_enrollments != 0:
                baker.make('calendar.Participation', event=activity, _quantity=num_enrollments)
        # 20 activities with limited enrollments between three weeks ago and three weeks from now,
        # with between 0 and 10 enrollments
        self.stdout.write("- 20 activities with limited enrollments and 0 to 10 enrollments, "
                          "between 3 weeks ago and 3 weeks from now...")
        as_limited_enroll = baker.make(ACTIVITY_MODEL_STRING,
                                       begin=gen_datetime_between(
                                           min_date=timezone.now() - timedelta(weeks=3),
                                           max_date=timezone.now() + timedelta(weeks=3)
                                       ),
                                       end=gen_datetime_between(
                                           min_date=timezone.now() - timedelta(weeks=3),
                                           max_date=timezone.now() + timedelta(weeks=3)
                                       ),
                                       maximum=gen_integer_between(10, 1000),
                                       enrollment=True,
                                       enrollment_begin=gen_datetime_between(
                                           min_date=timezone.now() - timedelta(weeks=3),
                                           max_date=timezone.now() + timedelta(weeks=3)
                                       ),
                                       enrollment_end=gen_datetime_between(
                                           min_date=timezone.now() - timedelta(weeks=3),
                                           max_date=timezone.now() + timedelta(weeks=3)
                                       ),
                                       _quantity=20)
        for activity in as_limited_enroll:
            num_enrollments = random.randint(0, 10)
            if num_enrollments != 0:
                baker.make('calendar.Participation', event=activity, _quantity=num_enrollments)
        # TODO: Enrollment options
        # Add between 1 and 30 pictures to the 20 limited enrollment activities
        self.stdout.write("- Between 1 and 30 pictures for the 20 limited enrollment activities...")
        attachment_recipe = Recipe('files.Attachment', _create_files=True, file=gen_image_by_dimensions(800, 600),
                                   public=gen_coinflip)
        for activity in as_limited_enroll:
            amount = random.randint(1, 30)
            attachments = attachment_recipe.make(_quantity=amount)
            activity.photos.set(attachments)
            activity.save()

        ###
        # Personal Tab models
        ###
        self.stdout.write("Creating random models from the Personal Tab module...")
        # Create 6 categories
        self.stdout.write("- 6 personal tab categories with 4 articles each...")
        categories = baker.make('personal_tab.Category', _quantity=6)
        # Create 4 products in each category
        for category in categories:
            article_recipe = Recipe('personal_tab.Article', _create_files=True, category=category)
            article_recipe.make(_quantity=4)

        ##
        # Create random objects in the other smaller modules that might be interesting
        ##
        self.stdout.write("Creating random models for the other modules...")
        # 20 About Pages
        self.stdout.write("- 20 about pages...")
        baker.make('about.Page', _quantity=20)
        # 10 Companies
        self.stdout.write("- 10 companies...")
        baker.make('companies.Company', _quantity=10)
        # 10 Website banners
        self.stdout.write("- 10 website banners...")
        websitebanner_recipe = Recipe('companies.WebsiteBanner', _create_files=True)
        websitebanner_recipe.make(_quantity=10)
        # 10 Television banners
        self.stdout.write("- 10 television banners...")
        televisionbanner_recipe = Recipe('companies.TelevisionBanner', _create_files=True)
        televisionbanner_recipe.make(_quantity=10)
        # 5 CompanyEvents
        self.stdout.write("- 5 company events...")
        baker.make('companies.CompanyEvent',
                   begin=gen_datetime_between(
                       min_date=timezone.now() - timedelta(weeks=3),
                       max_date=timezone.now() + timedelta(weeks=3)
                   ),
                   end=gen_datetime_between(
                       min_date=timezone.now() - timedelta(weeks=3),
                       max_date=timezone.now() + timedelta(weeks=3)
                   ),
                   visible_from=gen_datetime_between(
                       min_date=timezone.now() - timedelta(weeks=3),
                       max_date=timezone.now() + timedelta(weeks=3)
                   ),
                   visible_till=gen_datetime_between(
                       min_date=timezone.now() - timedelta(weeks=3),
                       max_date=timezone.now() + timedelta(weeks=3)
                   ),
                   _quantity=5)
        # 2 Education Page Categories
        self.stdout.write("- 2 education page categories...")
        baker.make('education.Category', _quantity=2)
        # 5 Education Pages
        self.stdout.write("- 5 education pages...")
        baker.make('education.Page', _quantity=5)
        # 5 Courses
        self.stdout.write("- 5 courses...")
        baker.make('education.Course', _quantity=5)
        # 5 Complaints
        self.stdout.write("- 5 complaints...")
        baker.make('education.Complaint', _quantity=5)
        # 20 Complaint Comments
        self.stdout.write("- 20 complaint comments...")
        baker.make('education.ComplaintComment', _quantity=20)
        # 5 EducationEvents
        self.stdout.write("- 5 education events...")
        baker.make('education.EducationEvent',
                   begin=gen_datetime_between(
                       min_date=timezone.now() - timedelta(weeks=3),
                       max_date=timezone.now() + timedelta(weeks=3)
                   ),
                   end=gen_datetime_between(
                       min_date=timezone.now() - timedelta(weeks=3),
                       max_date=timezone.now() + timedelta(weeks=3)
                   ),
                   _quantity=5)
        # 5 GMMs
        self.stdout.write("- 5 GMMs...")
        gmm_recipe = Recipe('gmm.GMM', agenda="")
        gmm_recipe.make(_quantity=5)
        # 20 News Items
        self.stdout.write("- 5 news items...")
        baker.make('news.NewsItem', _quantity=20)

        # One oAuth application with a random token
        self.stdout.write("- 1 sample oAuth application...")
        superuser = User.objects.filter(is_superuser=True).first()
        oauth_app = Application.objects.create(user=superuser, client_type=Application.CLIENT_CONFIDENTIAL,
                                          authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
                                          name="Sample oAuth Application")
        self.stdout.write("  Created \"{}\":".format(oauth_app.name))
        self.stdout.write("    client_id = \"{}\"".format(oauth_app.client_id))
        self.stdout.write("    client_secret = \"{}\"".format(oauth_app.client_secret))

        # Generate thumbnails for all Attachments
        self.stdout.write("Generating thumbnails...")
        for a in Attachment.objects.all():
            a.create_thumbnails()
            a.save()

        # Done
        self.stdout.write("Done!\n")

        # Notify of superuser account details
        if admin_username is not None:
            self.stdout.write("A superuser was created with username '{}'.".format(admin_username))
            if not enter_details:
                self.stdout.write("The password for this account is '{}'".format(admin_password))
            else:
                self.stdout.write("The password for this account was given earlier.")

        # TODO: First user authorization, Company corner, Education news, Education awards
