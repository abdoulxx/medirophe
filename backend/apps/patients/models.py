"""Modèle Patient — MVP `docs/MVP.md` §3 tâche 4 (Clinique & Labo) : identité,
résidence et antécédents (personnels + familiaux) d'un patient, sans les
modules avancés (génomique, oncologie, imagerie, dons, grossesse...) qui
restent hors périmètre (voir `docs/MVP.md` §4) et arriveront avec les
futures apps `consultations`/`ai_engine`. Champs alignés sur l'écran réel de
création "Dossier patient" du prototype (identité, résidence, antécédents
familiaux père/mère/fratrie). Partagé entre les rôles clinique (médecin/
biologiste) : un dossier patient n'appartient pas à qui l'a créé,
contrairement à un `User` (voir `apps/patients/permissions.py`, pas de
restriction objet par créateur).
"""
import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Sexe(models.TextChoices):
    HOMME = "homme", _("Homme")
    FEMME = "femme", _("Femme")


class SituationMatrimoniale(models.TextChoices):
    CELIBATAIRE = "celibataire", _("Célibataire")
    MARIE = "marie", _("Marié(e)")
    DIVORCE = "divorce", _("Divorcé(e)")
    VEUF = "veuf", _("Veuf/Veuve")


class LienParente(models.TextChoices):
    CONJOINT = "conjoint", _("Conjoint(e)")
    PARENT = "parent", _("Parent")
    ENFANT = "enfant", _("Enfant")
    FRATRIE = "fratrie", _("Frère/Sœur")
    AMI = "ami", _("Ami(e)")
    AUTRE = "autre", _("Autre")


class GroupeSanguin(models.TextChoices):
    A_POSITIF = "A+", "A+"
    A_NEGATIF = "A-", "A-"
    B_POSITIF = "B+", "B+"
    B_NEGATIF = "B-", "B-"
    AB_POSITIF = "AB+", "AB+"
    AB_NEGATIF = "AB-", "AB-"
    O_POSITIF = "O+", "O+"
    O_NEGATIF = "O-", "O-"


# Pathologies à cases à cocher du formulaire "Antécédents familiaux" — listes
# fixes (une par parent, le formulaire n'en propose pas d'autres), stockées en
# JSONField plutôt qu'une table de référence séparée (pas de besoin de
# gestion CRUD dessus, juste une liste plate à valider côté serializer).
PERE_PATHOLOGIES_CHOICES = ["hypertension", "cancer_prostate", "maladie_cardiaque", "avc", "cancer_autre"]
MERE_PATHOLOGIES_CHOICES = ["hypertension", "cancer_sein", "maladie_cardiaque", "avc", "cancer_autre"]


class Patient(models.Model):
    """Dossier patient. `numero_dossier` est généré côté serveur (jamais
    fourni par le client) pour garantir son unicité — le prototype mock
    (`patientsDB`) utilise un format libre (ex. `LB-4471`) non fiable comme
    identifiant unique réel, voir CLAUDE.md.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero_dossier = models.CharField(_("numéro de dossier"), max_length=20, unique=True, editable=False)

    # --- 1. Identité --------------------------------------------------
    first_name = models.CharField(_("prénom"), max_length=150)
    last_name = models.CharField(_("nom"), max_length=150)
    date_naissance = models.DateField(_("date de naissance"))
    sexe = models.CharField(_("sexe"), max_length=10, choices=Sexe.choices)
    nationalite = models.CharField(_("nationalité"), max_length=100, blank=True)
    situation_matrimoniale = models.CharField(
        _("situation matrimoniale"), max_length=20, choices=SituationMatrimoniale.choices, blank=True
    )
    nombre_enfants = models.PositiveSmallIntegerField(
        _("nombre d'enfants"), null=True, blank=True, validators=[MaxValueValidator(30)]
    )
    profession = models.CharField(_("profession"), max_length=150, blank=True)
    telephone = models.CharField(_("téléphone"), max_length=30, blank=True)
    email = models.EmailField(_("email"), blank=True)
    cni = models.CharField(_("numéro CNI"), max_length=30, blank=True)
    contact_urgence_nom = models.CharField(_("nom du contact d'urgence"), max_length=150, blank=True)
    contact_urgence_telephone = models.CharField(_("téléphone du contact d'urgence"), max_length=30, blank=True)
    contact_urgence_lien = models.CharField(
        _("lien de parenté du contact d'urgence"), max_length=20, choices=LienParente.choices, blank=True
    )

    # --- 2. Informations médicales générales ---------------------------
    groupe_sanguin = models.CharField(
        _("groupe sanguin"), max_length=3, choices=GroupeSanguin.choices, blank=True
    )
    taille_cm = models.PositiveSmallIntegerField(
        _("taille (cm)"), null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(300)]
    )
    poids_kg = models.DecimalField(
        _("poids (kg)"),
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(500)],
    )
    allergies = models.TextField(_("allergies"), blank=True)
    antecedents = models.TextField(_("antécédents personnels"), blank=True)
    antecedents_chirurgicaux = models.TextField(_("antécédents chirurgicaux"), blank=True)
    traitements_en_cours = models.TextField(_("traitements en cours"), blank=True)

    # --- 3. Résidence ----------------------------------------------------
    ville = models.CharField(_("ville"), max_length=100, blank=True)
    commune = models.CharField(_("commune"), max_length=100, blank=True)
    quartier = models.CharField(_("quartier"), max_length=100, blank=True)

    # --- Compte associé pour les urgences --------------------------------
    # Reste un simple indicateur : un vrai "compte" pour le contact d'urgence
    # impliquerait un portail d'authentification dédié pour des tiers non
    # membres du personnel clinique, ce qui est un système à part entière
    # (hors périmètre de ce module — voir CLAUDE.md si ça devient un besoin
    # réel) et non un champ de plus sur `Patient`.
    a_contact_urgence_associe = models.BooleanField(_("contact d'urgence associé"), default=False)

    is_active = models.BooleanField(
        _("dossier actif"), default=True,
        help_text=_("Archivage réversible d'un dossier créé par erreur ou obsolète — préférer à la suppression."),
    )

    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="patients_created",
        help_text=_("Membre du personnel clinique ayant créé le dossier."),
    )
    created_at = models.DateTimeField(_("créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("modifié le"), auto_now=True)

    class Meta:
        verbose_name = _("patient")
        verbose_name_plural = _("patients")
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.numero_dossier} — {self.last_name} {self.first_name}"

    def save(self, *args, **kwargs):
        if not self.numero_dossier:
            self.numero_dossier = f"MR-{self.id.hex[:8].upper()}"
        super().save(*args, **kwargs)

    @property
    def imc(self):
        """Indice de masse corporelle, calculé (jamais stocké — évite toute
        désynchronisation avec taille_cm/poids_kg, même logique que les champs
        dérivés `comboTitle`/`aiSynth` du prototype, volontairement absents
        du modèle réel)."""
        if not self.taille_cm or not self.poids_kg:
            return None
        taille_m = self.taille_cm / 100
        return round(float(self.poids_kg) / (taille_m**2), 1)


class AntecedentsFamiliaux(models.Model):
    """Antécédents familiaux (père/mère/fratrie) — section 4 de l'écran de
    création "Dossier patient" du prototype. Modèle séparé (OneToOne) plutôt
    que des champs directement sur `Patient` : section optionnelle, souvent
    vide/incomplète, qu'il est plus propre de ne créer qu'à la demande.

    `*_numero_dossier` reste un champ texte libre (pas de ForeignKey vers un
    autre `Patient`) : le patient peut connaître le numéro de dossier d'un
    parent sans que celui-ci soit forcément déjà enregistré dans ce système,
    et le rapprochement/dédoublonnage entre dossiers est explicitement hors
    périmètre MVP (`docs/MVP.md` §3 tâche 4 : "sans dédoublonnage avancé").
    """

    patient = models.OneToOneField(
        Patient, primary_key=True, on_delete=models.CASCADE, related_name="antecedents_familiaux"
    )

    # Père
    pere_numero_dossier = models.CharField(_("numéro de dossier du père"), max_length=20, blank=True)
    pere_vivant = models.BooleanField(_("père vivant"), null=True, blank=True)
    pere_age = models.PositiveSmallIntegerField(
        _("âge du père"), null=True, blank=True, validators=[MaxValueValidator(120)]
    )
    pere_diabetique = models.BooleanField(_("père diabétique"), null=True, blank=True)
    pere_pathologies = models.JSONField(_("autres pathologies du père"), default=list, blank=True)

    # Mère
    mere_numero_dossier = models.CharField(_("numéro de dossier de la mère"), max_length=20, blank=True)
    mere_vivante = models.BooleanField(_("mère vivante"), null=True, blank=True)
    mere_age = models.PositiveSmallIntegerField(
        _("âge de la mère"), null=True, blank=True, validators=[MaxValueValidator(120)]
    )
    mere_diabetique = models.BooleanField(_("mère diabétique"), null=True, blank=True)
    mere_pathologies = models.JSONField(_("autres pathologies de la mère"), default=list, blank=True)

    # Frère / Sœur (entrée générique, une seule fratrie représentative)
    fratrie_telephone = models.CharField(_("téléphone du frère/de la sœur"), max_length=30, blank=True)
    fratrie_numero_dossier = models.CharField(_("numéro de dossier du frère/de la sœur"), max_length=20, blank=True)
    fratrie_vivant = models.BooleanField(_("frère/sœur vivant(e)"), null=True, blank=True)
    fratrie_age = models.PositiveSmallIntegerField(
        _("âge du frère/de la sœur"), null=True, blank=True, validators=[MaxValueValidator(120)]
    )
    fratrie_cancer = models.BooleanField(_("frère/sœur atteint(e) de cancer"), null=True, blank=True)
    fratrie_diabetique = models.BooleanField(_("frère/sœur diabétique"), null=True, blank=True)
    fratrie_drepanocytose = models.BooleanField(_("frère/sœur drépanocytaire"), null=True, blank=True)

    # Autres antécédents (grands-parents...)
    autres_antecedents_familiaux = models.BooleanField(_("autres antécédents familiaux connus"), default=False)

    class Meta:
        verbose_name = _("antécédents familiaux")
        verbose_name_plural = _("antécédents familiaux")

    def __str__(self):
        return f"Antécédents familiaux — {self.patient.numero_dossier}"
