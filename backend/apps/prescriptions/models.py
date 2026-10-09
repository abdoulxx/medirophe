"""Modèle Prescription (d'examen) — MVP `docs/MVP.md` §3 tâche 6 (Clinique &
Labo), construit en une fois sans découpage MVP (voir CLAUDE.md
"2026-09-28") : la demande d'examen de laboratoire, écran "Prescrire un
examen" / "Enregistrer un examen" du prototype.

Contrairement à `apps.consultations.Consultation` (écriture réservée au
médecin), ce module autorise aussi le biologiste en écriture : le prototype
permet au biologiste d'enregistrer une demande d'examen de façon autonome,
sans passer par une consultation médicale (écran "Enregistrer un examen",
`renderPrescribeExamPage()`), en plus du cas où le médecin prescrit des
examens depuis sa consultation (`dc-confirm`). Un `Prescription` peut donc
exister sans `consultation` liée (champ optionnel) — voir `permissions.py`.

`Examen` est un référentiel statique (103 lignes, catalogue `examTable` du
prototype — ~ligne 22452), même pattern que `apps.consultations.Service` :
table de référence, seedée par migration de données, exposée en lecture
seule. Les colonnes cliniques du prototype (`normal`, `crit`, `options` —
plages de référence, seuils critiques, choix de résultat qualitatifs) ne
sont PAS reprises ici : elles relèvent de l'interprétation d'un *résultat*
d'examen, donc de la future app "Saisie & validation de résultat" (tâche 7),
pas de la prescription elle-même. Même limite pour `EXAM_VALIDITY_*`
(durée de validité d'un résultat avant nouvel examen) : moteur de règles
cliniques, hors périmètre de ce module.

`montant_fcfa` n'est jamais fourni par le client : calculé côté serveur à
partir du prix catalogue des examens liés (même logique anti-falsification
que `Patient.numero_dossier`/`Consultation.medecin`) — voir `serializers.py`.
"""
import uuid

from django.core.validators import MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.consultations.models import Consultation, TypeCouverture
from apps.patients.models import Patient


class CategorieExamen(models.TextChoices):
    """Les 17 catégories du catalogue `examTable` du prototype."""

    METABOLISME = "metabolisme", _("Métabolisme")
    RENAL = "renal", _("Rénal")
    HEPATIQUE = "hepatique", _("Hépatique")
    INFLAMMATION = "inflammation", _("Inflammation")
    HEMATOLOGIE = "hematologie", _("Hématologie")
    ENDOCRINOLOGIE = "endocrinologie", _("Endocrinologie")
    CARDIOLOGIE = "cardiologie", _("Cardiologie")
    VITAMINES_MINERAUX = "vitamines_mineraux", _("Vitamines & minéraux")
    INFECTIOLOGIE_SEROLOGIE = "infectiologie_serologie", _("Infectiologie / Sérologie")
    GYNECOLOGIE_CYTOLOGIE = "gynecologie_cytologie", _("Gynécologie / Cytologie")
    COAGULATION = "coagulation", _("Coagulation")
    MARQUEURS_TUMORAUX = "marqueurs_tumoraux", _("Marqueurs tumoraux")
    HORMONAL_FERTILITE = "hormonal_fertilite", _("Hormonal / Fertilité")
    IMMUNOLOGIE_ALLERGIE = "immunologie_allergie", _("Immunologie / Allergie")
    PARASITOLOGIE_MICROBIOLOGIE = "parasitologie_microbiologie", _("Parasitologie / Microbiologie")
    TOXICOLOGIE = "toxicologie", _("Toxicologie")
    BILAN_PRENATAL_GROSSESSE = "bilan_prenatal_grossesse", _("Bilan prénatal / Grossesse")


class StatutPrescription(models.TextChoices):
    """Mirroir de `statusMap` du prototype (~ligne 5972)."""

    SAISIE = "saisie", _("En cours de traitement")
    VALIDATION = "validation", _("En validation")
    VALIDE = "valide", _("Terminé")
    URGENT = "urgent", _("Cas urgent signalé")
    RECOMMANDE = "recommande", _("Recommandé par médecin")
    REJETE = "rejete", _("Échantillon rejeté — nouveau prélèvement requis")


class ModePaiement(models.TextChoices):
    """Mirroir de `paymentLabels` du prototype (~ligne 5992)."""

    ESPECES = "especes", _("Espèces")
    MOBILE = "mobile", _("Mobile Money")
    CARTE = "carte", _("Carte bancaire")
    CHEQUE = "cheque", _("Chèque")
    AUTRE = "autre", _("Autre")


class Examen(models.Model):
    """Référentiel des examens de laboratoire proposables à la prescription
    (catalogue `examTable` du prototype, 103 entrées). Donnée de référence
    statique, gérée via l'admin/fixtures — voir `apps.consultations.Service`
    pour le même pattern. Exposé en lecture seule via
    `GET /api/v1/prescriptions/examens/`."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(_("code"), max_length=10, unique=True)
    nom = models.CharField(_("nom"), max_length=200, unique=True)
    categorie = models.CharField(_("catégorie"), max_length=30, choices=CategorieExamen.choices)
    unite = models.CharField(_("unité"), max_length=20, blank=True)
    taux_cmu = models.PositiveSmallIntegerField(
        _("taux de couverture CMU (%)"), validators=[MaxValueValidator(100)]
    )
    prix_fcfa = models.PositiveIntegerField(_("prix (FCFA)"))
    duree_estimee = models.CharField(_("délai de rendu estimé"), max_length=20, blank=True)
    actif = models.BooleanField(_("actif"), default=True)

    class Meta:
        verbose_name = _("examen (référentiel)")
        verbose_name_plural = _("examens (référentiel)")
        ordering = ["categorie", "nom"]

    def __str__(self):
        return f"{self.nom} ({self.code})"


class Prescription(models.Model):
    """Demande d'examen(s) de laboratoire. `patient` est requis à la création
    mais immuable ensuite (voir `serializers.py`, même protection que
    `Consultation.patient`) ; `consultation` est optionnelle (cas "sans
    consultation associée" du prototype) et également immuable une fois
    posée, pour la même raison."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero_demande = models.CharField(_("numéro de demande"), max_length=20, unique=True, editable=False)

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="prescriptions_examens")
    consultation = models.ForeignKey(
        Consultation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="prescriptions_examens",
        help_text=_("Consultation d'origine, si la demande est rattachée à une consultation médicale."),
    )
    cree_par = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="prescriptions_examens_creees",
        help_text=_("Médecin ou biologiste ayant enregistré la demande."),
    )

    statut = models.CharField(
        _("statut"), max_length=12, choices=StatutPrescription.choices, default=StatutPrescription.SAISIE
    )
    urgent = models.BooleanField(_("urgent"), default=False)
    motif = models.TextField(_("motif / note pour le laboratoire"), blank=True)

    type_couverture = models.CharField(
        _("type de couverture"), max_length=10, choices=TypeCouverture.choices, default=TypeCouverture.AUCUNE
    )
    numero_couverture = models.CharField(_("n° de couverture (CMU / mutuelle)"), max_length=100, blank=True)
    mode_paiement = models.CharField(
        _("mode de paiement"), max_length=10, choices=ModePaiement.choices, default=ModePaiement.ESPECES
    )
    montant_fcfa = models.PositiveIntegerField(
        _("montant (FCFA)"),
        default=0,
        editable=False,
        help_text=_("Calculé côté serveur à partir du prix catalogue des examens liés — jamais fourni par le client."),
    )

    created_at = models.DateTimeField(_("créée le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("modifiée le"), auto_now=True)

    class Meta:
        verbose_name = _("prescription d'examen")
        verbose_name_plural = _("prescriptions d'examens")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.numero_demande} — {self.patient.numero_dossier}"

    def save(self, *args, **kwargs):
        if not self.numero_demande:
            self.numero_demande = f"REQ-{self.id.hex[:8].upper()}"
        super().save(*args, **kwargs)

    def recalculer_montant(self):
        """Recalcule et persiste `montant_fcfa` à partir des examens liés.
        Appelé par le serializer après toute écriture des lignes
        `examens_prescrits` (création, ou remplacement complet à la mise à
        jour) — jamais déduit d'une valeur envoyée par le client."""
        total = sum(
            self.examens_prescrits.select_related("examen").values_list("examen__prix_fcfa", flat=True)
        )
        self.montant_fcfa = total
        self.save(update_fields=["montant_fcfa"])


class ExamenPrescrit(models.Model):
    """Ligne d'examen individuelle au sein d'une demande (`Prescription`).
    Toujours écrite avec la prescription elle-même (serializer imbriqué,
    remplacement complet à la mise à jour) — jamais via un endpoint propre,
    même logique que `apps.consultations.PrescriptionMedicament`.

    `examen` référence le catalogue (`PROTECT` : on ne peut pas supprimer un
    examen du référentiel tant qu'il est cité dans une demande existante)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name="examens_prescrits")
    examen = models.ForeignKey(Examen, on_delete=models.PROTECT, related_name="+")

    class Meta:
        verbose_name = _("ligne d'examen prescrit")
        verbose_name_plural = _("lignes d'examen prescrit")
        constraints = [
            models.UniqueConstraint(fields=["prescription", "examen"], name="unique_examen_par_prescription")
        ]

    def __str__(self):
        return f"{self.examen.nom} — {self.prescription.numero_demande}"
