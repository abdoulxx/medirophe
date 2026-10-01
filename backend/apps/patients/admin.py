from django.contrib import admin

from .models import AntecedentsFamiliaux, Patient


class AntecedentsFamiliauxInline(admin.StackedInline):
    model = AntecedentsFamiliaux
    can_delete = True
    extra = 0


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    ordering = ["last_name", "first_name"]
    list_display = ["numero_dossier", "last_name", "first_name", "sexe", "date_naissance", "is_active", "created_at"]
    list_filter = ["sexe", "groupe_sanguin", "is_active"]
    search_fields = ["numero_dossier", "last_name", "first_name", "cni", "telephone", "email"]
    readonly_fields = ["numero_dossier", "created_at", "updated_at"]
    inlines = [AntecedentsFamiliauxInline]
