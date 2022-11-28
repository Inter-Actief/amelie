from django.contrib import admin
from django.forms import inlineformset_factory

from amelie.education.models import Period, Complaint, ComplaintComment, Course, EducationEvent, Module


#
# Admin pages
#
class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'course_code', 'name')
    search_fields = ('course_code', 'name')


class CourseInline(admin.TabularInline):
    model = Course
    fk_name = 'module_ptr'
    can_delete = False
    readonly_fields = ('name', 'course_code')
    extra = 0


class ModuleAdmin(admin.ModelAdmin):
    list_display = ('id', 'course_code', 'name')
    search_fields = ('course_code', 'name')

    inlines = [
        CourseInline
    ]


class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('course', 'subject', 'summary', 'public', 'anonymous', 'completed')


class EducationEventAdmin(admin.ModelAdmin):
    list_display = ('summary', 'begin', 'end', 'education_organizer', 'public')


admin.site.register(Module, ModuleAdmin)
admin.site.register(Course, CourseAdmin)
admin.site.register(Period)
admin.site.register(Complaint, ComplaintAdmin)
admin.site.register(ComplaintComment)
admin.site.register(EducationEvent, EducationEventAdmin)
