from django.contrib import admin

from .models import ConseilPatient, Consultation, PrescriptionMedicament, RendezVousSuivi, Service


class PrescriptionMedicamentInline(admin.TabularInline):
    model = PrescriptionMedicament
    extra = 0


class RendezVousSuiviInline(admin.TabularInline):
    model = RendezVousSuivi
    extra = 0


class ConseilPatientInline(admin.TabularInline):
    model = ConseilPatient
    extra = 0


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    ordering = ["-created_at"]
    list_display = ["patient", "medecin", "type_consultation", "statut", "urgence", "created_at"]
    list_filter = ["type_consultation", "statut", "type_couverture", "urgence"]
    search_fields = ["patient__numero_dossier", "patient__last_name", "patient__first_name", "motif"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [PrescriptionMedicamentInline, RendezVousSuiviInline, ConseilPatientInline]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    ordering = ["categorie", "nom"]
    list_display = ["nom", "categorie"]
    list_filter = ["categorie"]
    search_fields = ["nom"]
