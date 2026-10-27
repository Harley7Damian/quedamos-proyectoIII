from django.contrib import admin

from .models import AssistantLink, Availability, MeetingRequest

admin.site.register(AssistantLink)


@admin.register(MeetingRequest)
class MeetingRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "executive", "created_by", "counterpart_name", "status", "created_at")
    list_filter = ("status",)


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ("request", "party", "updated_at")
