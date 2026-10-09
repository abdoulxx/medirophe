from django.contrib import admin

from .models import Examen, ExamenPrescrit, Prescription


class ExamenPrescritInline(admin.TabularInline):
    model = ExamenPrescrit
    extra = 0
    autocomplete_fields = ["examen"]


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    ordering = ["-created_at"]
    list_display = ["numero_demande", "patient", "statut", "urgent", "montant_fcfa", "created_at"]
    list_filter = ["statut", "urgent", "type_couverture", "mode_paiement"]
    search_fields = ["numero_demande", "patient__numero_dossier", "patient__last_name", "patient__first_name"]
    readonly_fields = ["numero_demande", "montant_fcfa", "created_at", "updated_at"]
    inlines = [ExamenPrescritInline]


@admin.register(Examen)
class ExamenAdmin(admin.ModelAdmin):
    ordering = ["categorie", "nom"]
    list_display = ["nom", "code", "categorie", "prix_fcfa", "taux_cmu", "actif"]
    list_filter = ["categorie", "actif"]
    search_fields = ["nom", "code"]
