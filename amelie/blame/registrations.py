from auditlog.registry import auditlog

import amelie
from amelie.activities.models import Activity
from amelie.claudia.models import ExtraGroup, SharedDrive, ExtraPerson, AliasGroup, Mapping, Contact, ExtraPersonalAlias
from amelie.companies.models import Company, CompanyEvent, BaseBanner, WebsiteBanner, TelevisionBanner
from amelie.calendar.models import Event
from amelie.members.models import Person, Committee, Faculty, Department, Study, Dogroup, \
    DogroupGeneration, Association, PaymentType, CommitteeCategory, Function
from amelie.news.models import NewsItem
from amelie.narrowcasting.models import TelevisionPromotion
from amelie.education.models import Category, Page, EducationEvent, Complaint, ComplaintComment
from amelie.about.models import Page as AboutPage
from amelie.personal_tab.models import DiscountPeriod, CustomTransaction, LedgerAccount, Article, \
    Category as CookieCornerCategory, AuthorizationType, Authorization, Amendment
from amelie.weekmail.models import WeekMail

"""
Register your models to the auditlog here. This is done in a central place to keep a good
overview of which models are logged and which are not.
"""

# Activity hooks
auditlog.register(Activity)

# Company hooks
auditlog.register(Company)
auditlog.register(CompanyEvent)
auditlog.register(BaseBanner)
auditlog.register(WebsiteBanner, exclude_fields=['views'])
auditlog.register(TelevisionBanner)

# Calendar hooks
auditlog.register(Event)

# Member hooks
auditlog.register(Faculty)
auditlog.register(Department)
auditlog.register(Study)
auditlog.register(Dogroup)
auditlog.register(DogroupGeneration)
auditlog.register(Association)
auditlog.register(PaymentType)
auditlog.register(Person, include_fields=["first_name", "last_name_prefix", "last_name", "initials", "slug", "picture",
                                          "date_of_birth", "email_address", "account_name", "shell", "webmaster",
                                          "user"])
auditlog.register(amelie.members.models.Membership)
auditlog.register(Committee)
auditlog.register(CommitteeCategory)
auditlog.register(Function)

# Narrowcasting hooks
auditlog.register(TelevisionPromotion)

# News hooks
auditlog.register(NewsItem)

# Education hooks
auditlog.register(Category)
auditlog.register(Page)
auditlog.register(EducationEvent)
auditlog.register(Complaint)
auditlog.register(ComplaintComment)

# Over hooks
auditlog.register(AboutPage)

# Personal Tab hooks
auditlog.register(DiscountPeriod)
auditlog.register(CustomTransaction)
auditlog.register(LedgerAccount)
auditlog.register(Article)
auditlog.register(CookieCornerCategory)
auditlog.register(AuthorizationType)
auditlog.register(Authorization)
auditlog.register(Amendment)

# Week mailing hooks
auditlog.register(WeekMail)

# Claudia hooks
auditlog.register(ExtraGroup)
auditlog.register(SharedDrive)
auditlog.register(ExtraPerson)
auditlog.register(AliasGroup)
auditlog.register(ExtraPersonalAlias)
auditlog.register(Contact)
auditlog.register(Mapping)
auditlog.register(amelie.claudia.models.Membership)
