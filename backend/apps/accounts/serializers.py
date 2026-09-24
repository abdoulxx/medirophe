from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User
from .password_reset import get_user_from_uid, token_generator


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Ajoute `role`/`email` dans le payload du JWT (utile côté client pour
    adapter l'UI sans appel réseau supplémentaire). Le token expirant en 15
    minutes, un changement de rôle est répercuté rapidement malgré ce cache.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        return token


class UserSelfSerializer(serializers.ModelSerializer):
    """Vue "mon profil". Champs explicites (jamais `fields = "__all__"") :
    `role`, `is_active`, `is_staff` sont en lecture seule ici pour qu'un
    utilisateur ne puisse jamais s'auto-élever de privilèges via un simple
    PATCH (protection mass assignment).
    """

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role", "is_active", "date_joined"]
        read_only_fields = ["id", "email", "role", "is_active", "date_joined"]


class UserAdminSerializer(serializers.ModelSerializer):
    """Vue "liste/détail des utilisateurs" côté Ministère (super admin),
    en lecture (GET) : tous les champs exposés sont en lecture seule ici,
    l'écriture passe par `UserCreateSerializer`/`UserAdminUpdateSerializer`.
    """

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role", "is_active", "date_joined"]
        read_only_fields = fields


class UserCreateSerializer(serializers.ModelSerializer):
    """Création de compte par un super admin (`POST /users/`). Champs
    explicites : `is_staff`/`is_superuser` ne sont volontairement pas
    exposés ici (ne serviraient qu'à /admin/, jamais à accorder via l'API) ;
    un extra `is_staff: true` dans le payload est simplement ignoré par DRF,
    pas une faille de mass assignment.
    """

    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role", "password"]

    def validate(self, attrs):
        # Instance non sauvegardée : permet à UserAttributeSimilarityValidator
        # de comparer le mot de passe à l'email/nom/prénom de CE compte,
        # comme le ferait Django pour un formulaire de création classique.
        temp_user = User(
            email=attrs.get("email", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        try:
            validate_password(attrs["password"], user=temp_user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserAdminUpdateSerializer(serializers.ModelSerializer):
    """Mise à jour d'un compte tiers par un super admin (`PATCH /users/<uuid>/`).
    Seuls `role` et `is_active` sont modifiables ici — changer l'email (identifiant
    de connexion) mériterait un flux dédié avec re-vérification, hors périmètre
    actuel ; le mot de passe ne se change que via `ChangePasswordSerializer`,
    jamais en écrasant `password` par un admin.
    """

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role", "is_active", "date_joined"]
        read_only_fields = ["id", "email", "first_name", "last_name", "date_joined"]


class ChangePasswordSerializer(serializers.Serializer):
    """Changement de son propre mot de passe (`POST /me/change-password/`).
    Exige l'ancien mot de passe (empêche un attaquant en session déjà ouverte
    mais qui ne connaît pas le mot de passe, ex. poste laissé déverrouillé,
    de verrouiller le compte légitime hors de portée)."""

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Mot de passe actuel incorrect.")
        return value

    def validate_new_password(self, value):
        user = self.context["request"].user
        try:
            validate_password(value, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs):
        if attrs["old_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "Le nouveau mot de passe doit différer de l'ancien."}
            )
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    """"Mot de passe oublié" (`POST /auth/password-reset/`). Ne renseigne
    jamais si l'email existe ou non — c'est la vue qui répond un message
    générique dans tous les cas (non-énumérable, même logique que le login).
    """

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Confirmation du reset (`POST /auth/password-reset/confirm/`), avec le
    `uid`/`token` reçus par email. Un `uid`/`token` invalide, expiré, ou déjà
    consommé (un reset ou changement de mot de passe antérieur invalide le
    token via `PasswordResetTokenGenerator`) renvoie la même erreur générique
    — pas de distinction qui aiderait à deviner un état interne.
    """

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = get_user_from_uid(attrs["uid"])
        if user is None or not token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError(
                {"token": "Lien de réinitialisation invalide ou expiré."}
            )
        try:
            validate_password(attrs["new_password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc
        attrs["user"] = user
        return attrs
