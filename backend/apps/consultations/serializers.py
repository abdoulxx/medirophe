from rest_framework import serializers

from apps.accounts.roles import Role
from apps.patients.models import Sexe

from .models import (
    ConseilPatient,
    Consultation,
    MotifCategorie,
    PrescriptionMedicament,
    RendezVousSuivi,
    Service,
    StatutConsultation,
    TypeCouverture,
)


def _validate_items(value, required_keys, field_name):
    """Valide la forme (liste d'objets contenant au moins `required_keys`)
    des champs JSON à vocabulaire libre (symptômes, antécédents, traitements
    en cours) — pas de liste de choix fermée, voir models.py."""
    if not isinstance(value, list):
        raise serializers.ValidationError(f"{field_name} doit être une liste.")
    for item in value:
        if not isinstance(item, dict) or not required_keys.issubset(item.keys()):
            raise serializers.ValidationError(
                f"Chaque élément de {field_name} doit être un objet contenant au moins : {sorted(required_keys)}."
            )
    return value


class ServiceSerializer(serializers.ModelSerializer):
    """Référentiel en lecture (voir `GET /api/v1/consultations/services/`
    dans `views.py`) — pas d'endpoint d'écriture, catalogue géré via l'admin."""

    class Meta:
        model = Service
        fields = ["id", "categorie", "nom", "role_principal"]


class PrescriptionMedicamentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrescriptionMedicament
        fields = ["id", "medicament", "posologie", "duree", "quantite", "instructions"]
        read_only_fields = ["id"]


class RendezVousSuiviSerializer(serializers.ModelSerializer):
    class Meta:
        model = RendezVousSuivi
        fields = ["id", "date_rdv", "heure_rdv", "motif", "note"]
        read_only_fields = ["id"]


class ConseilPatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConseilPatient
        fields = ["id", "label", "texte"]
        read_only_fields = ["id"]


class ConsultationSerializer(serializers.ModelSerializer):
    """Champs explicites (jamais `fields = "__all__"`, voir CLAUDE.md).
    `medecin` est en lecture seule : renseigné depuis `request.user` par la
    vue, jamais par le client (même protection anti mass-assignment que
    `Patient.created_by`).

    `prescriptions`, `rendez_vous_suivi` et `conseils_patient` sont des
    sous-ressources imbriquées écrites/relues en bloc avec la consultation :
    à la mise à jour, fournir la clé remplace entièrement les lignes
    existantes (pas de diff ligne à ligne) — elles ne sont jamais adressables
    individuellement via l'API, voir models.py.

    `patient` est requis à la création mais immuable ensuite (ignoré par
    `update()`, voir plus bas) — sans ça, un `PATCH` pourrait rattacher une
    consultation existante à un autre dossier patient.
    """

    imc = serializers.FloatField(read_only=True)
    prescriptions = PrescriptionMedicamentSerializer(many=True, required=False)
    rendez_vous_suivi = RendezVousSuiviSerializer(many=True, required=False)
    conseils_patient = ConseilPatientSerializer(many=True, required=False)
    services_orientation_detail = ServiceSerializer(source="services_orientation", many=True, read_only=True)

    class Meta:
        model = Consultation
        fields = [
            "id",
            "patient",
            "medecin",
            "type_consultation",
            "statut",
            "type_couverture",
            "numero_couverture",
            "urgence",
            "medecin_oriente",
            "services_orientation",
            "services_orientation_detail",
            "motif_categories",
            "motif",
            "grossesse_en_cours",
            "grossesse_trimestre",
            "poids_kg",
            "taille_cm",
            "imc",
            "temperature_c",
            "frequence_cardiaque",
            "pression_arterielle_systolique",
            "pression_arterielle_diastolique",
            "frequence_respiratoire",
            "spo2",
            "glycemie_capillaire",
            "diurese",
            "symptomes",
            "autres_symptomes",
            "antecedents_mentionnes",
            "tabac",
            "alcool",
            "allergies_signalees",
            "allergies_detail",
            "hypothese_diagnostique",
            "traitements_en_cours",
            "observations",
            "recommandation",
            "commentaire_medecin",
            "prescriptions",
            "rendez_vous_suivi",
            "conseils_patient",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "medecin", "created_at", "updated_at"]

    def validate_symptomes(self, value):
        return _validate_items(value, {"label"}, "symptomes")

    def validate_antecedents_mentionnes(self, value):
        return _validate_items(value, {"label"}, "antecedents_mentionnes")

    def validate_traitements_en_cours(self, value):
        return _validate_items(value, {"nom"}, "traitements_en_cours")

    def validate_motif_categories(self, value):
        # Liste fermée (16 valeurs cochables à l'étape Admission), contrairement
        # à symptomes/antecedents_mentionnes/traitements_en_cours qui restent à
        # vocabulaire libre — voir models.py.
        if not isinstance(value, list):
            raise serializers.ValidationError("motif_categories doit être une liste.")
        valid_values = set(MotifCategorie.values)
        invalid = [item for item in value if item not in valid_values]
        if invalid:
            raise serializers.ValidationError(f"Valeur(s) invalide(s) : {invalid}.")
        return value

    def validate_medecin_oriente(self, value):
        if value is not None and value.role != Role.MEDECIN:
            raise serializers.ValidationError("Le médecin orienté doit avoir le rôle médecin.")
        return value

    def validate(self, attrs):
        grossesse_en_cours = attrs.get("grossesse_en_cours", getattr(self.instance, "grossesse_en_cours", False))
        grossesse_trimestre = attrs.get("grossesse_trimestre", getattr(self.instance, "grossesse_trimestre", None))
        if grossesse_trimestre and not grossesse_en_cours:
            raise serializers.ValidationError({"grossesse_trimestre": "Nécessite grossesse_en_cours=true."})

        patient = attrs.get("patient", getattr(self.instance, "patient", None))
        if grossesse_en_cours and patient is not None and patient.sexe != Sexe.FEMME:
            raise serializers.ValidationError(
                {"grossesse_en_cours": "Non applicable : le patient sélectionné n'est pas renseigné comme femme."}
            )

        type_couverture = attrs.get("type_couverture", getattr(self.instance, "type_couverture", TypeCouverture.AUCUNE))
        numero_couverture = attrs.get("numero_couverture", getattr(self.instance, "numero_couverture", ""))
        if type_couverture != TypeCouverture.AUCUNE and not numero_couverture:
            raise serializers.ValidationError(
                {"numero_couverture": "Requis lorsque type_couverture n'est pas 'aucune'."}
            )
        return attrs

    def create(self, validated_data):
        prescriptions_data = validated_data.pop("prescriptions", [])
        rdv_data = validated_data.pop("rendez_vous_suivi", [])
        conseils_data = validated_data.pop("conseils_patient", [])
        services = validated_data.pop("services_orientation", None)
        consultation = Consultation.objects.create(**validated_data)
        if services is not None:
            consultation.services_orientation.set(services)
        for item in prescriptions_data:
            PrescriptionMedicament.objects.create(consultation=consultation, **item)
        for item in rdv_data:
            RendezVousSuivi.objects.create(consultation=consultation, **item)
        for item in conseils_data:
            ConseilPatient.objects.create(consultation=consultation, **item)
        return consultation

    def update(self, instance, validated_data):
        # `patient` ne se modifie jamais après création — même protection que
        # `medecin` (lecture seule), mais via pop() plutôt que read_only_fields
        # puisque le champ reste requis à la création (voir docstring ci-dessus).
        validated_data.pop("patient", None)
        prescriptions_data = validated_data.pop("prescriptions", None)
        rdv_data = validated_data.pop("rendez_vous_suivi", None)
        conseils_data = validated_data.pop("conseils_patient", None)
        services = validated_data.pop("services_orientation", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if services is not None:
            instance.services_orientation.set(services)

        if prescriptions_data is not None:
            instance.prescriptions.all().delete()
            for item in prescriptions_data:
                PrescriptionMedicament.objects.create(consultation=instance, **item)

        if rdv_data is not None:
            instance.rendez_vous_suivi.all().delete()
            for item in rdv_data:
                RendezVousSuivi.objects.create(consultation=instance, **item)

        if conseils_data is not None:
            instance.conseils_patient.all().delete()
            for item in conseils_data:
                ConseilPatient.objects.create(consultation=instance, **item)

        return instance
