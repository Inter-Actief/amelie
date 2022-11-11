from django.contrib import admin

from amelie.members.models import Department, Payment, PaymentType, Committee, CommitteeCategory, Dogroup, \
    DogroupGeneration, Faculty, Function, Membership, MembershipType, Employee, Person, Student, Study, \
    StudyPeriod, Association, Preference, PreferenceCategory, UnverifiedEnrollment
from amelie.tools.admin import NameAdmin, DescriptionAdmin, AbbreviationAdmin, AbbreviationTypeAdmin


class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'membership', 'payment_type', 'date', 'amount')
    search_fields = ('membership__member__first_name', 'membership__member__last_name',)
    list_filter = ('payment_type', 'amount', 'membership__type', 'membership__year',)
    date_hierarchy = 'date'
    raw_id_fields = ('membership',)


class CommitteeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'abbreviation', 'category', 'superuser',)
    search_fields = ('name', 'abbreviation')
    list_filter = ('category', 'superuser',)


class DogroupGenerationAdmin(admin.ModelAdmin):
    list_display = ('id', 'dogroup', 'generation')
    search_fields = ('generation', 'dogroup__name')
    list_filter = ('dogroup', 'generation',)
    filter_horizontal = ('parents',)


class PreferenceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'preference_nl', 'preference_en', 'category', 'default',)
    list_filter = ('category', 'default', 'adjustable', 'first_time', 'print',)
    search_fields = ('name', 'preference_nl', 'preference_en',)


class PersonAdmin(admin.ModelAdmin):
    list_display = ('id', '__str__', 'is_member', 'is_active_member', 'has_user')
    search_fields = ('first_name', 'last_name_prefix', 'last_name')
    list_filter = ('gender', 'country', 'preferred_language', 'preferences',)
    date_hierarchy = 'date_of_birth'


class StudentAdmin(admin.ModelAdmin):
    list_display = ('id', 'person', 'number')
    search_fields = ('person__first_name', 'person__last_name', 'number')


class StudyPeriodAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'study', 'begin', 'end', 'graduated')
    search_fields = ('student__person__first_name', 'student__person__last_name', 'student__number',
                     'study__name_nl', 'study__name_en',)
    list_filter = ('graduated', 'study',)
    date_hierarchy = 'begin'
    raw_id_fields = ('student',)


class MembershipTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name_nl', 'name_en', 'description', 'price', 'active')
    list_filter = ('active',)


class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('id', 'person', 'number')
    search_fields = ('person__first_name', 'person__last_name', 'number')


class MembershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'member', 'year', 'type',)
    search_fields = ('member__first_name', 'member__last_name',)
    list_filter = ('year', 'type', 'ended',)
    list_per_page = 50


class FunctionAdmin(admin.ModelAdmin):
    list_display = ('id', 'person', 'committee', 'function', 'begin', 'end')
    search_fields = ('person__first_name', 'person__last_name', 'committee__name', 'function', 'note')
    list_filter = ('begin', 'end',)
    date_hierarchy = 'begin'


class StudyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name_nl', 'name_en', 'abbreviation', 'type', 'primary_study', 'active')
    search_fields = ('name_nl', 'name_en', 'abbreviation')
    list_filter = ('type',)


# Stop, hook time, tuh duh duh duh, tuh duh, tuh duh, *can* touch this
admin.site.register(Function, FunctionAdmin)
admin.site.register(Committee, CommitteeAdmin)
admin.site.register(CommitteeCategory, NameAdmin)
admin.site.register(Payment, PaymentAdmin)
admin.site.register(Membership, MembershipAdmin)
admin.site.register(Employee, EmployeeAdmin)
admin.site.register(StudyPeriod, StudyPeriodAdmin)
admin.site.register(Student, StudentAdmin)
admin.site.register(PaymentType, DescriptionAdmin)
admin.site.register(MembershipType, MembershipTypeAdmin)
admin.site.register(Person, PersonAdmin)
admin.site.register(Preference, PreferenceAdmin)
admin.site.register(PreferenceCategory)
admin.site.register(Association, NameAdmin)
admin.site.register(Dogroup, NameAdmin)
admin.site.register(DogroupGeneration, DogroupGenerationAdmin)
admin.site.register(Faculty, AbbreviationAdmin)
admin.site.register(Department, AbbreviationTypeAdmin)
admin.site.register(Study, StudyAdmin)
admin.site.register(UnverifiedEnrollment)
