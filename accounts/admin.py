from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Profile, User


@admin.register(User)
class QuedamosUserAdmin(UserAdmin):
    list_display = ("full_name", "username", "role", "link_code", "is_staff")
    list_filter = ("role", "is_staff")
    fieldsets = UserAdmin.fieldsets + (("Quedamos", {"fields": ("full_name", "role")}),)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "area", "work_start", "work_end", "onboarding_completed_at", "onboarding_skipped_at")
    list_filter = ("area",)
