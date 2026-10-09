from rest_framework import serializers

from .models import Examen, ExamenPrescrit, Prescription, TypeCouverture


class ExamenSerializer(serializers.ModelSerializer):
    """Référentiel en lecture (voir `GET /api/v1/prescriptions/examens/`
    dans `views.py`) — pas d'endpoint d'écriture, catalogue géré via l'admin."""

    class Meta:
        model = Examen
        fields = ["id", "code", "nom", "categorie", "unite", "taux_cmu", "prix_fcfa", "duree_estimee", "actif"]


class ExamenPrescritSerializer(serializers.ModelSerializer):
    examen_detail = ExamenSerializer(source="examen", read_only=True)

    class Meta:
        model = ExamenPrescrit
        fields = ["id", "examen", "examen_detail"]
        read_only_fields = ["id"]


class PrescriptionSerializer(serializers.ModelSerializer):
    """Champs explicites (jamais `fields = "__all__"`, voir CLAUDE.md).
    `cree_par`/`numero_demande`/`montant_fcfa` sont en lecture seule :
    `cree_par` est renseigné depuis `request.user` par la vue (même
    protection anti mass-assignment que `Consultation.medecin`),
    `numero_demande` est généré côté modèle, `montant_fcfa` est recalculé
    côté serveur à partir du prix catalogue des examens liés (jamais une
    valeur fournie par le client).

    `examens_prescrits` est une sous-ressource imbriquée écrite/relue en
    bloc avec la prescription : à la mise à jour, fournir la clé remplace
    entièrement les lignes existantes (pas de diff ligne à ligne), même
    logique que `apps.consultations.ConsultationSerializer`. Au moins un
    examen est requis à la création (règle métier du prototype : "Veuillez
    sélectionner au moins un examen").

    `patient` et `consultation` sont requis/acceptés à la création mais
    immuables ensuite (ignorés par `update()`, voir plus bas) — sans ça, un
    `PATCH` pourrait rattacher une demande existante à un autre dossier ou à
    une autre consultation.
    """

    examens_prescrits = ExamenPrescritSerializer(many=True)

    class Meta:
        model = Prescription
        fields = [
            "id",
            "numero_demande",
            "patient",
            "consultation",
            "cree_par",
            "statut",
            "urgent",
            "motif",
            "type_couverture",
            "numero_couverture",
            "mode_paiement",
            "montant_fcfa",
            "examens_prescrits",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "numero_demande", "cree_par", "montant_fcfa", "created_at", "updated_at"]

    def validate_examens_prescrits(self, value):
        if not value:
            raise serializers.ValidationError("Veuillez sélectionner au moins un examen.")
        examen_ids = [item["examen"].id for item in value]
        if len(examen_ids) != len(set(examen_ids)):
            raise serializers.ValidationError("Un même examen ne peut pas être sélectionné plusieurs fois.")
        return value

    def validate(self, attrs):
        consultation = attrs.get("consultation", getattr(self.instance, "consultation", None))
        patient = attrs.get("patient", getattr(self.instance, "patient", None))
        if consultation is not None and patient is not None and consultation.patient_id != patient.id:
            raise serializers.ValidationError(
                {"consultation": "La consultation sélectionnée n'appartient pas à ce patient."}
            )

        type_couverture = attrs.get("type_couverture", getattr(self.instance, "type_couverture", TypeCouverture.AUCUNE))
        numero_couverture = attrs.get("numero_couverture", getattr(self.instance, "numero_couverture", ""))
        if type_couverture != TypeCouverture.AUCUNE and not numero_couverture:
            raise serializers.ValidationError(
                {"numero_couverture": "Requis lorsque type_couverture n'est pas 'aucune'."}
            )
        return attrs

    def create(self, validated_data):
        examens_data = validated_data.pop("examens_prescrits")
        prescription = Prescription.objects.create(**validated_data)
        for item in examens_data:
            ExamenPrescrit.objects.create(prescription=prescription, **item)
        prescription.recalculer_montant()
        return prescription

    def update(self, instance, validated_data):
        # `patient`/`consultation` ne se modifient jamais après création —
        # même protection que `medecin` sur Consultation (lecture seule),
        # mais via pop() puisque `patient` reste requis à la création.
        validated_data.pop("patient", None)
        validated_data.pop("consultation", None)
        examens_data = validated_data.pop("examens_prescrits", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if examens_data is not None:
            instance.examens_prescrits.all().delete()
            for item in examens_data:
                ExamenPrescrit.objects.create(prescription=instance, **item)
            instance.recalculer_montant()

        return instance
