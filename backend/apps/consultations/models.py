"""Modèle Consultation — MVP `docs/MVP.md` §3 tâche 5 (Clinique & Labo),
étendu sans découpage MVP (voir CLAUDE.md "2026-09-28") : c'est l'acte
médical réalisé par un médecin sur un patient existant — motif, constantes,
symptômes, antécédents, hypothèse diagnostique — avec ses deux sous-
ressources imbriquées (prescriptions médicamenteuses, rendez-vous de suivi),
toujours écrites en même temps que la consultation elle-même (pas d'endpoint
séparé), comme dans l'écran "Démarrer une consultation" du prototype.

Inclut aussi les champs de l'étape "Admission & Pré-consultation" qui précède
la consultation dans le prototype (couverture santé, orientation vers un ou
plusieurs services + médecin orienté, statut urgent/non urgent, motif par
catégories cochables) — regroupés sur ce même modèle plutôt que dans un
modèle "Admission" séparé, car cette étape n'a pas de cycle de vie propre
hors de la consultation qu'elle précède.

La prescription d'examen de laboratoire ("Prescrire un examen" dans le
prototype) est volontairement hors de ce module : c'est un écran distinct
dans le prototype, avec son propre cycle de vie (statut de résultat, lien
optionnel vers une consultation) — elle arrivera dans sa propre app, par
cohérence avec le découpage `docs/MVP.md` §3 (tâches 5/6/7 = Consultation,
Prescription d'examen, Résultats labo, trois tâches distinctes).

Pas de restriction objet par créateur, comme `Patient` : une consultation
appartient au dossier partagé du patient, lisible par tout le personnel
clinique (voir `permissions.py`), mais seul un médecin peut l'écrire —
`medecin` est en lecture seule côté serializer, renseigné depuis
`request.user` à la création (même protection anti mass-assignment que
`Patient.created_by`).
"""
import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.patients.models import Patient


class TypeConsultation(models.TextChoices):
    PREMIERE = "premiere", _("Première consultation")
    SUIVI = "suivi", _("Consultation de suivi")
    URGENCE = "urgence", _("Consultation d'urgence")
    TELEMEDECINE = "telemedecine", _("Télémédecine")
    PRE_OPERATOIRE = "pre_operatoire", _("Consultation pré-opératoire")
    AUTRE = "autre", _("Autre")


class StatutConsultation(models.TextChoices):
    EN_COURS = "en_cours", _("En cours")
    TERMINEE = "terminee", _("Terminée")
    ANNULEE = "annulee", _("Annulée")


class Tabac(models.TextChoices):
    NON = "non", _("Non")
    SEVRE = "sevre", _("Sevré")
    ACTIF = "actif", _("Actif")


class Alcool(models.TextChoices):
    NON = "non", _("Non")
    OCCASIONNEL = "occasionnel", _("Occasionnel")
    REGULIER = "regulier", _("Régulier")


class TypeCouverture(models.TextChoices):
    AUCUNE = "aucune", _("Aucune — patient payant")
    CMU = "cmu", _("CMU")
    MUTUELLE = "mutuelle", _("Mutuelle / assurance privée")


class MotifCategorie(models.TextChoices):
    """Catégories de motif cochables à l'étape "Admission & Pré-consultation"
    du prototype (liste fermée de 16 valeurs, contrairement à `symptomes`/
    `antecedents_mentionnes` qui sont à vocabulaire libre) — chacune associée
    dans le prototype à un service cible indicatif (texte d'aide UI, non
    persisté ici)."""

    EXAMENS_BIOLOGIQUES = "examens_biologiques", _("Examens biologiques")
    IMAGERIE_MEDICALE = "imagerie_medicale", _("Imagerie médicale")
    SOINS_TECHNIQUES = "soins_techniques", _("Soins techniques")
    CONSULTATIONS_MEDICALES = "consultations_medicales", _("Consultations médicales")
    URGENCES = "urgences", _("Urgences")
    CHIRURGIE = "chirurgie", _("Chirurgie")
    SUIVI_CHRONIQUE = "suivi_chronique", _("Suivi chronique")
    PREVENTION_DEPISTAGE = "prevention_depistage", _("Prévention / Dépistage")
    GROSSESSE_ACCOUCHEMENT = "grossesse_accouchement", _("Grossesse / Accouchement")
    PEDIATRIE = "pediatrie", _("Pédiatrie")
    GERIATRIE = "geriatrie", _("Gériatrie")
    SANTE_MENTALE = "sante_mentale", _("Santé mentale")
    READAPTATION = "readaptation", _("Réadaptation")
    SOINS_PALLIATIFS = "soins_palliatifs", _("Soins palliatifs")
    ADMINISTRATIF = "administratif", _("Administratif")
    DON_DE_SANG = "don_de_sang", _("Don de sang")


class ServiceCategorie(models.TextChoices):
    CLINIQUE = "clinique", _("Services cliniques")
    FONCTIONNEL = "fonctionnel", _("Services fonctionnels (plateaux techniques)")
    SUPPORT = "support", _("Services de support")
    TRANSVERSAL = "transversal", _("Services transversaux")


class Service(models.Model):
    """Référentiel des services hospitaliers vers lesquels orienter un patient
    à l'étape "Admission & Pré-consultation" (section "➡️ Orientation" du
    prototype — 47 services répartis en 4 catégories). Donnée de référence
    statique (catalogue), gérée via l'admin/fixtures, pas via l'API publique —
    exposée en lecture seule via `GET /api/v1/consultations/services/` pour
    que le futur frontend construise le sélecteur sans la recoder en dur
    (contrairement au prototype HTML, qui la hardcode en JS)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    categorie = models.CharField(_("catégorie"), max_length=20, choices=ServiceCategorie.choices)
    nom = models.CharField(_("nom"), max_length=150, unique=True)
    role_principal = models.TextField(_("rôle principal"), blank=True)

    class Meta:
        verbose_name = _("service")
        verbose_name_plural = _("services")
        ordering = ["categorie", "nom"]

    def __str__(self):
        return self.nom


class Consultation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="consultations")
    medecin = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="consultations",
        help_text=_("Médecin ayant réalisé la consultation."),
    )

    type_consultation = models.CharField(
        _("type de consultation"),
        max_length=20,
        choices=TypeConsultation.choices,
        default=TypeConsultation.PREMIERE,
    )
    statut = models.CharField(
        _("statut"), max_length=10, choices=StatutConsultation.choices, default=StatutConsultation.EN_COURS
    )

    # --- Admission & pré-consultation ---------------------------------
    # Capturées dans le prototype à une étape distincte ("Admission &
    # Pré-consultation", avant l'étape "Consultation" elle-même), mais
    # modélisées ici sur le même objet `Consultation` plutôt que dans un
    # modèle séparé : une admission n'a pas de cycle de vie propre hors de la
    # consultation qu'elle précède (pas de sous-ressource adressable à part,
    # même logique que `prescriptions`/`rendez_vous_suivi`).
    type_couverture = models.CharField(
        _("type de couverture"), max_length=10, choices=TypeCouverture.choices, default=TypeCouverture.AUCUNE
    )
    numero_couverture = models.CharField(_("n° de couverture (CMU / mutuelle)"), max_length=100, blank=True)
    urgence = models.BooleanField(_("statut urgent"), default=False)
    medecin_oriente = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="consultations_orientees",
        help_text=_("Médecin vers lequel le patient est orienté à l'admission (distinct de `medecin`, l'auteur)."),
    )
    services_orientation = models.ManyToManyField(
        Service, blank=True, related_name="consultations", verbose_name=_("services d'orientation")
    )

    # --- Motif et contexte clinique -----------------------------------
    motif_categories = models.JSONField(_("catégories de motif"), default=list, blank=True)
    motif = models.TextField(_("motif principal"))
    grossesse_en_cours = models.BooleanField(_("grossesse en cours"), default=False)
    grossesse_trimestre = models.PositiveSmallIntegerField(
        _("trimestre de grossesse"), null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(3)]
    )

    # --- Signes vitaux & anthropométrie -------------------------------
    poids_kg = models.DecimalField(
        _("poids (kg)"),
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(500)],
    )
    taille_cm = models.PositiveSmallIntegerField(
        _("taille (cm)"), null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(300)]
    )
    temperature_c = models.DecimalField(
        _("température (°C)"),
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(30), MaxValueValidator(45)],
    )
    frequence_cardiaque = models.PositiveSmallIntegerField(
        _("fréquence cardiaque (bpm)"), null=True, blank=True, validators=[MaxValueValidator(300)]
    )
    pression_arterielle_systolique = models.PositiveSmallIntegerField(
        _("pression artérielle systolique (mmHg)"), null=True, blank=True, validators=[MaxValueValidator(300)]
    )
    pression_arterielle_diastolique = models.PositiveSmallIntegerField(
        _("pression artérielle diastolique (mmHg)"), null=True, blank=True, validators=[MaxValueValidator(200)]
    )
    frequence_respiratoire = models.PositiveSmallIntegerField(
        _("fréquence respiratoire (/min)"), null=True, blank=True, validators=[MaxValueValidator(100)]
    )
    spo2 = models.PositiveSmallIntegerField(_("SpO₂ (%)"), null=True, blank=True, validators=[MaxValueValidator(100)])
    glycemie_capillaire = models.DecimalField(
        _("glycémie capillaire"), max_digits=5, decimal_places=1, null=True, blank=True, validators=[MaxValueValidator(600)]
    )
    diurese = models.CharField(_("diurèse"), max_length=100, blank=True)

    # --- Symptômes & antécédents --------------------------------------
    # Listes libres (pas un vocabulaire fermé, le prototype propose toujours
    # une case "autres" en plus des choix suggérés) : JSONField plutôt qu'une
    # table de référence, validé en forme (liste d'objets) côté serializer.
    symptomes = models.JSONField(_("symptômes"), default=list, blank=True)
    autres_symptomes = models.TextField(_("autres symptômes"), blank=True)
    antecedents_mentionnes = models.JSONField(_("antécédents personnels & mode de vie"), default=list, blank=True)
    tabac = models.CharField(_("tabac"), max_length=10, choices=Tabac.choices, blank=True)
    alcool = models.CharField(_("alcool"), max_length=12, choices=Alcool.choices, blank=True)
    allergies_signalees = models.BooleanField(_("allergies signalées"), default=False)
    allergies_detail = models.TextField(_("détail des allergies"), blank=True)

    # --- Évaluation médicale ------------------------------------------
    hypothese_diagnostique = models.TextField(_("hypothèse diagnostique"), blank=True)
    traitements_en_cours = models.JSONField(_("traitements en cours"), default=list, blank=True)
    observations = models.TextField(_("observations / notes cliniques"), blank=True)
    recommandation = models.TextField(_("recommandation"), blank=True)
    commentaire_medecin = models.TextField(_("commentaire du médecin"), blank=True)

    created_at = models.DateTimeField(_("créée le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("modifiée le"), auto_now=True)

    class Meta:
        verbose_name = _("consultation")
        verbose_name_plural = _("consultations")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Consultation {self.patient.numero_dossier} — {self.created_at:%Y-%m-%d}"

    @property
    def imc(self):
        """Calculé (jamais stocké), snapshot du poids/taille pris à CETTE
        consultation — distinct de `Patient.imc`, qui reflète le dossier
        général et peut dater d'une autre visite."""
        if not self.taille_cm or not self.poids_kg:
            return None
        taille_m = self.taille_cm / 100
        return round(float(self.poids_kg) / (taille_m**2), 1)


class PrescriptionMedicament(models.Model):
    """Ligne d'ordonnance. Pas de modèle "Prescription" (ordonnance) séparé :
    une consultation produit au plus une ordonnance, donc une simple liste de
    lignes rattachées directement à la consultation suffit (pas d'abstraction
    prématurée). Toujours écrite avec la consultation elle-même (serializer
    imbriqué), jamais via un endpoint propre — voir `serializers.py`."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name="prescriptions")
    medicament = models.CharField(_("médicament"), max_length=200)
    posologie = models.CharField(_("posologie"), max_length=200, blank=True)
    duree = models.CharField(_("durée du traitement"), max_length=100, blank=True)
    quantite = models.PositiveSmallIntegerField(
        _("quantité"), null=True, blank=True, validators=[MaxValueValidator(1000)]
    )
    instructions = models.TextField(_("instructions"), blank=True)

    class Meta:
        verbose_name = _("ligne de prescription")
        verbose_name_plural = _("lignes de prescription")

    def __str__(self):
        return f"{self.medicament} — {self.consultation_id}"


class ConseilPatient(models.Model):
    """Conseil au patient validé par le médecin à l'étape "Récapitulatif" du
    prototype (section "🩺 Conseils au patient" — cartes générées depuis les
    hypothèses diagnostiques retenues, que le médecin accepte, modifie ou
    refuse ; seuls les conseils non refusés sont conservés, voir
    `conseilsSaved`/`dc-confirm` dans le prototype). `label` identifie
    l'hypothèse/le conseil, `texte` est le texte final validé (accepté tel
    que généré, ou réécrit par le médecin). La génération elle-même
    (règles cliniques à partir des hypothèses/antécédents) reste côté
    prototype/futur module IA — seul le résultat validé est persisté ici,
    même logique imbriquée que `PrescriptionMedicament`/`RendezVousSuivi`."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name="conseils_patient")
    label = models.CharField(_("libellé"), max_length=200)
    texte = models.TextField(_("texte du conseil"), blank=True)

    class Meta:
        verbose_name = _("conseil au patient")
        verbose_name_plural = _("conseils au patient")

    def __str__(self):
        return f"{self.label} — {self.consultation_id}"


class RendezVousSuivi(models.Model):
    """Rendez-vous de suivi planifié à l'issue d'une consultation (étape
    "Récapitulatif" du prototype). Même logique imbriquée que
    `PrescriptionMedicament` — pas d'endpoint propre."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name="rendez_vous_suivi")
    date_rdv = models.DateField(_("date du rendez-vous"))
    heure_rdv = models.TimeField(_("heure du rendez-vous"), null=True, blank=True)
    motif = models.CharField(_("motif"), max_length=255, blank=True)
    note = models.TextField(_("note"), blank=True)
    created_at = models.DateTimeField(_("créé le"), auto_now_add=True)

    class Meta:
        verbose_name = _("rendez-vous de suivi")
        verbose_name_plural = _("rendez-vous de suivi")
        ordering = ["date_rdv", "heure_rdv"]

    def __str__(self):
        return f"RDV {self.date_rdv} — {self.consultation_id}"
