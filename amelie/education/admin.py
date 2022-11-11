from django.contrib import admin

from amelie.education.models import Period, Complaint, ComplaintComment, Course, EducationEvent


#
# Admin pages
#
class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'course_code', 'course_type', 'name')
    search_fields = ('course_code', 'name')


class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('course', 'subject', 'summary', 'public', 'anonymous', 'completed')


class EducationEventAdmin(admin.ModelAdmin):
    list_display = ('summary', 'begin', 'end', 'education_organizer', 'public')


admin.site.register(Course, CourseAdmin)
admin.site.register(Period)
admin.site.register(Complaint, ComplaintAdmin)
admin.site.register(ComplaintComment)
admin.site.register(EducationEvent, EducationEventAdmin)
