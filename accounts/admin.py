from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin

from .models import Profile, User


@admin.register(User)
class QuedamosUserAdmin(UserAdmin):
    """Control de cuentas para la persona administradora (superusuario).

    Una cuenta creada por error se elimina si no tiene actividad; si ya tiene reuniones se desactiva, así
    conserva el historial y no puede ingresar."""

    list_display = ("full_name", "username", "role", "is_active", "last_login", "date_joined", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("full_name", "username", "email")
    ordering = ("-date_joined",)
    actions = ("desactivar_cuentas", "reactivar_cuentas")
    fieldsets = UserAdmin.fieldsets + (("Quedamos", {"fields": ("full_name", "role")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Quedamos", {"fields": ("full_name", "role")}),)

    def save_model(self, request, obj, form, change):
        # El ingreso busca el correo en minúsculas: se guarda igual y se mantiene igual al campo de correo.
        obj.username = (obj.username or "").strip().lower()
        if "@" in obj.username:
            obj.email = obj.username
        super().save_model(request, obj, form, change)

    @admin.action(description="Desactivar cuentas seleccionadas (no podrán ingresar)")
    def desactivar_cuentas(self, request, queryset):
        cuentas = queryset.exclude(pk=request.user.pk)
        total = cuentas.update(is_active=False)
        if queryset.filter(pk=request.user.pk).exists():
            self.message_user(request, "Tu propia cuenta no se desactiva desde aquí.", messages.WARNING)
        self.message_user(request, f"Cuentas desactivadas: {total}.", messages.SUCCESS)

    @admin.action(description="Reactivar cuentas seleccionadas")
    def reactivar_cuentas(self, request, queryset):
        self.message_user(request, f"Cuentas reactivadas: {queryset.update(is_active=True)}.", messages.SUCCESS)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "area", "telefono", "work_start", "work_end", "onboarding_completed_at", "onboarding_skipped_at")
    list_filter = ("area",)
    search_fields = ("user__full_name", "user__username", "telefono")
