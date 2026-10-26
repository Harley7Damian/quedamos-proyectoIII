from django.contrib import admin

from .models import AssistantLink, MeetingRequest

admin.site.register(AssistantLink)


@admin.register(MeetingRequest)
class MeetingRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "executive", "created_by", "counterpart_name", "status", "created_at")
    list_filter = ("status",)
