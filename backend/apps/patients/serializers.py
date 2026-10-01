from datetime import date

from rest_framework import serializers

from .models import AntecedentsFamiliaux, MERE_PATHOLOGIES_CHOICES, PERE_PATHOLOGIES_CHOICES, Patient


class AntecedentsFamiliauxSerializer(serializers.ModelSerializer):
    """Section 4 du formulaire de création patient. Toujours optionnelle :
    absente de la réponse tant qu'aucune information familiale n'a été
    saisie (voir `PatientSerializer.get_antecedents_familiaux`)."""

    pere_pathologies = serializers.ListField(
        child=serializers.ChoiceField(choices=PERE_PATHOLOGIES_CHOICES), required=False
    )
    mere_pathologies = serializers.ListField(
        child=serializers.ChoiceField(choices=MERE_PATHOLOGIES_CHOICES), required=False
    )

    class Meta:
        model = AntecedentsFamiliaux
        fields = [
            "pere_numero_dossier",
            "pere_vivant",
            "pere_age",
            "pere_diabetique",
            "pere_pathologies",
            "mere_numero_dossier",
            "mere_vivante",
            "mere_age",
            "mere_diabetique",
            "mere_pathologies",
            "fratrie_telephone",
            "fratrie_numero_dossier",
            "fratrie_vivant",
            "fratrie_age",
            "fratrie_cancer",
            "fratrie_diabetique",
            "fratrie_drepanocytose",
            "autres_antecedents_familiaux",
        ]


class PatientSerializer(serializers.ModelSerializer):
    """Champs explicites (jamais `fields = "__all__"`, voir CLAUDE.md).
    `numero_dossier` est en lecture seule : généré côté serveur (`Patient.save`),
    jamais fourni/modifiable par le client.

    `antecedents_familiaux` est un sous-objet optionnel (section 4 du
    formulaire) : `update()`/`create()` le gèrent via `get_or_create` (relation
    OneToOne 1-1, jamais de dédoublonnage à gérer — un seul enregistrement
    possible par patient).
    """

    imc = serializers.FloatField(read_only=True)
    antecedents_familiaux = AntecedentsFamiliauxSerializer(required=False)

    class Meta:
        model = Patient
        fields = [
            "id",
            "numero_dossier",
            "first_name",
            "last_name",
            "date_naissance",
            "sexe",
            "nationalite",
            "situation_matrimoniale",
            "nombre_enfants",
            "profession",
            "telephone",
            "email",
            "cni",
            "contact_urgence_nom",
            "contact_urgence_telephone",
            "contact_urgence_lien",
            "groupe_sanguin",
            "taille_cm",
            "poids_kg",
            "imc",
            "allergies",
            "antecedents",
            "antecedents_chirurgicaux",
            "traitements_en_cours",
            "ville",
            "commune",
            "quartier",
            "a_contact_urgence_associe",
            "antecedents_familiaux",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "numero_dossier", "created_by", "created_at", "updated_at"]

    def validate_date_naissance(self, value):
        if value > date.today():
            raise serializers.ValidationError("La date de naissance ne peut pas être dans le futur.")
        return value

    def create(self, validated_data):
        antecedents_data = validated_data.pop("antecedents_familiaux", None)
        # `is_active` reste ignoré à la création : un dossier archivé avant
        # même d'exister n'a pas de sens, l'archivage est une action distincte
        # (PATCH) réservée à un dossier déjà créé.
        validated_data.pop("is_active", None)
        patient = Patient.objects.create(**validated_data)
        if antecedents_data:
            AntecedentsFamiliaux.objects.create(patient=patient, **antecedents_data)
        return patient

    def update(self, instance, validated_data):
        antecedents_data = validated_data.pop("antecedents_familiaux", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if antecedents_data is not None:
            AntecedentsFamiliaux.objects.update_or_create(patient=instance, defaults=antecedents_data)

        return instance
