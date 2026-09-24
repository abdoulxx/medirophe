"""
Vues API du module accounts : auth JWT (login/refresh/logout, mot de passe
oublié) + gestion des comptes (profil personnel, CRUD admin sur les tiers).

Chaque vue sensible journalise son action via `apps.audit.services.record`
après coup (succès réel, jamais avant) — voir CLAUDE.md "Audit log" pour la
liste des événements couverts. Les décisions de permission suivent toutes le
pattern décrit dans `permissions.py` : rôle (`HasRole`) pour "qui atteint ce
type de vue", objet (`has_object_permission`) pour "sur CETTE instance".
"""
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenBlacklistView, TokenObtainPairView, TokenRefreshView

from apps.audit.models import AuditAction
from apps.audit.services import record

from .models import User
from .password_reset import send_password_reset_email
from .permissions import IsSelfOrSuperAdmin, IsSuperAdmin
from .serializers import (
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserAdminSerializer,
    UserAdminUpdateSerializer,
    UserCreateSerializer,
    UserSelfSerializer,
)
from .throttling import LoginRateThrottle, PasswordResetRateThrottle

TAG_AUTH = "Authentification"
TAG_ACCOUNTS = "Comptes utilisateurs"


@extend_schema(
    tags=[TAG_AUTH],
    summary="Connexion",
    description=(
        "Retourne un couple `access` (15 min) / `refresh` (7 jours). "
        "À passer ensuite en en-tête `Authorization: Bearer <access>` sur "
        "toutes les routes protégées."
    ),
    examples=[
        OpenApiExample(
            "Requête",
            value={"email": "medecin@medirophe.test", "password": "un-mot-de-passe-valide"},
            request_only=True,
        ),
        OpenApiExample(
            "Connexion réussie",
            value={"access": "eyJhbGciOi...", "refresh": "eyJhbGciOi..."},
            response_only=True,
        ),
    ],
)
class CustomTokenObtainPairView(TokenObtainPairView):
    """Identique à `TokenObtainPairView` (email/mot de passe → access+refresh),
    mais avec un serializer qui ajoute `role`/`email` dans le payload du JWT
    et un throttle anti brute-force par IP (voir `throttling.py`)."""

    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        email = request.data.get("email", "")
        try:
            response = super().post(request, *args, **kwargs)
        except Exception:
            # Le serializer lève (401) avant tout retour de post() : sans ce
            # try/except, l'échec ne repasserait jamais par ce code.
            record(AuditAction.LOGIN_FAILED, actor_email=email, request=request)
            raise

        user = User.objects.filter(email__iexact=email).first()
        record(AuditAction.LOGIN_SUCCESS, actor=user, request=request)
        return response


@extend_schema(
    tags=[TAG_AUTH],
    summary="Rafraîchir le token d'accès",
    description=(
        "Échange un `refresh` token contre un nouveau couple access/refresh "
        "(rotation). L'ancien `refresh` est immédiatement invalidé — le "
        "renvoyer une seconde fois répond 401."
    ),
)
class CustomTokenRefreshView(TokenRefreshView):
    pass


@extend_schema(
    tags=[TAG_AUTH],
    summary="Déconnexion",
    description="Invalide (blacklist) le `refresh` token fourni. L'`access` token déjà émis reste valable jusqu'à son expiration naturelle (≤ 15 min).",
)
class CustomTokenBlacklistView(TokenBlacklistView):
    def post(self, request, *args, **kwargs):
        # Décodé avant l'appel à super().post() : une fois le refresh token
        # blacklisté par l'opération elle-même, le reconstruire échouerait
        # (vérification anti-rejeu de RefreshToken), et on perdrait l'acteur.
        user = None
        try:
            token = RefreshToken(request.data.get("refresh", ""))
            user = User.objects.filter(pk=token["user_id"]).first()
        except TokenError:
            pass

        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            record(AuditAction.LOGOUT, actor=user, target_user=user, request=request)
        return response


@extend_schema(
    tags=[TAG_AUTH],
    summary="Mot de passe oublié",
    description=(
        "Envoie un email de réinitialisation si le compte existe et est "
        "actif. Répond 200 dans tous les cas, email connu ou non — évite "
        "d'énumérer les comptes existants, même logique que `/auth/token/`."
    ),
    examples=[
        OpenApiExample("Requête", value={"email": "utilisateur@medirophe.test"}, request_only=True),
    ],
)
class PasswordResetRequestView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = User.objects.get(email__iexact=serializer.validated_data["email"], is_active=True)
        except User.DoesNotExist:
            user = None

        if user is not None:
            send_password_reset_email(user)
            record(AuditAction.PASSWORD_RESET_REQUESTED, target_user=user, request=request)
        else:
            record(
                AuditAction.PASSWORD_RESET_REQUESTED,
                request=request,
                requested_email=serializer.validated_data["email"],
                account_found=False,
            )

        return Response({"detail": "Si ce compte existe, un email de réinitialisation vient d'être envoyé."})


@extend_schema(
    tags=[TAG_AUTH],
    summary="Confirmer la réinitialisation",
    description=(
        "`uid`/`token` reçus par email (voir `/auth/password-reset/`). En cas "
        "de succès, révoque immédiatement tous les `refresh` tokens déjà "
        "émis pour ce compte, comme `/accounts/me/change-password/`."
    ),
    examples=[
        OpenApiExample(
            "Requête",
            value={"uid": "MQ", "token": "abc123-xyz", "new_password": "nouveau-mot-de-passe-solide"},
            request_only=True,
        ),
    ],
)
class PasswordResetConfirmView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        for outstanding in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=outstanding)

        record(AuditAction.PASSWORD_RESET_CONFIRMED, target_user=user, request=request)

        return Response({"detail": "Mot de passe réinitialisé. Toutes les sessions ont été révoquées."})


@extend_schema_view(
    get=extend_schema(
        tags=[TAG_ACCOUNTS],
        summary="Mon profil",
        description="Profil de l'utilisateur authentifié (déduit du token, pas de paramètre d'URL).",
    ),
    patch=extend_schema(
        tags=[TAG_ACCOUNTS],
        summary="Modifier mon profil",
        description=(
            "Mise à jour partielle de son propre profil. Seuls `first_name`/"
            "`last_name` sont réellement modifiables : `role`/`is_active`/"
            "`email` envoyés dans le body sont silencieusement ignorés "
            "(protection anti mass-assignment), la réponse renvoie leur "
            "valeur inchangée."
        ),
    ),
)
class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH sur son propre profil uniquement — jamais de paramètre
    d'URL identifiant un autre utilisateur, donc pas de surface IDOR ici.

    Pas de PUT exposé : un remplacement complet forcerait le frontend à
    toujours renvoyer tous les champs modifiables sous peine de les vider,
    pour un bénéfice nul ici (PATCH suffit à tous les cas d'usage profil).
    """

    http_method_names = ["get", "patch", "head", "options"]
    permission_classes = [IsAuthenticated]
    serializer_class = UserSelfSerializer

    def get_object(self):
        return self.request.user


@extend_schema(
    tags=[TAG_ACCOUNTS],
    summary="Changer mon mot de passe",
    description=(
        "Exige l'ancien mot de passe. En cas de succès, révoque immédiatement "
        "tous les `refresh` tokens déjà émis pour ce compte (déconnexion "
        "forcée de toute autre session)."
    ),
    examples=[
        OpenApiExample(
            "Requête",
            value={"old_password": "ancien-mot-de-passe", "new_password": "nouveau-mot-de-passe-solide"},
            request_only=True,
        ),
    ],
)
class ChangePasswordView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        for outstanding in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=outstanding)

        record(AuditAction.PASSWORD_CHANGED, actor=user, target_user=user, request=request)

        return Response(
            {"detail": "Mot de passe mis à jour. Toutes les sessions ont été révoquées."},
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    get=extend_schema(
        tags=[TAG_ACCOUNTS],
        summary="Consulter un utilisateur",
        description="Sa propre fiche, ou n'importe quelle fiche si `super_admin`.",
    ),
    patch=extend_schema(
        tags=[TAG_ACCOUNTS],
        summary="Modifier le rôle/statut d'un utilisateur (désactivation incluse)",
        description=(
            "Réservé à `super_admin`. Seuls `role` et `is_active` sont "
            "modifiables (jamais `email`, jamais le mot de passe — voir "
            "`/me/change-password/` pour ça). Un utilisateur ne peut jamais "
            "atteindre cette route en écriture sur sa propre fiche : elle est "
            "verrouillée par rôle, pas seulement par objet.\n\n"
            "**C'est aussi la route de désactivation (soft-delete)** : "
            "`{\"is_active\": false}` bloque immédiatement le compte — "
            "SimpleJWT vérifie `is_active` à chaque requête authentifiée, "
            "donc même un access token encore valide cesse de fonctionner "
            "sans action supplémentaire. Préférer ceci à `DELETE` pour "
            "toute désactivation réversible (suspension, départ temporaire...)."
        ),
    ),
    delete=extend_schema(
        tags=[TAG_ACCOUNTS],
        summary="Supprimer définitivement un compte",
        description=(
            "Réservé à `super_admin`. Suppression physique et "
            "irréversible de la ligne `User` — à ne pas confondre avec la "
            "désactivation (`PATCH` avec `is_active: false`, réversible), "
            "qui doit rester le choix par défaut. Un admin ne peut pas "
            "supprimer son propre compte via cette route. L'action est "
            "journalisée (`user_deleted`) avant suppression effective, avec "
            "l'email du compte conservé dans le journal."
        ),
    ),
)
class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Double verrou, comme l'exige le RBAC objet :
    - `queryset` reste volontairement `User.objects.all()` ici, car la
      restriction "self ou super admin" ne peut se faire qu'objet par
      objet (l'admin doit pouvoir atteindre n'importe quel utilisateur) ;
    - c'est `IsSelfOrSuperAdmin.has_object_permission` qui borne la
      lecture croisée ; l'écriture (PATCH/DELETE), elle, est filtrée par
      rôle (`IsSuperAdmin`) avant même d'atteindre l'objet.

    Pas de PUT exposé, pour la même raison que sur `MeView`.
    """

    http_method_names = ["get", "patch", "delete", "head", "options"]
    queryset = User.objects.all()

    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [IsSuperAdmin()]
        return [IsSelfOrSuperAdmin()]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return UserAdminUpdateSerializer
        return UserAdminSerializer

    def perform_update(self, serializer):
        before = {"role": serializer.instance.role, "is_active": serializer.instance.is_active}
        user = serializer.save()
        record(
            AuditAction.USER_UPDATED,
            actor=self.request.user,
            target_user=user,
            request=self.request,
            before=before,
            after={"role": user.role, "is_active": user.is_active},
        )

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise PermissionDenied("Un admin ne peut pas supprimer son propre compte.")

        # Journalisé avant la suppression effective : `target_user` est mis
        # à NULL automatiquement par la cascade SET_NULL une fois l'instance
        # supprimée, mais `target_user_email` (dénormalisé) reste lisible.
        record(
            AuditAction.USER_DELETED,
            actor=self.request.user,
            target_user=instance,
            request=self.request,
            role=instance.role,
        )
        instance.delete()


@extend_schema_view(
    get=extend_schema(
        tags=[TAG_ACCOUNTS],
        summary="Lister les utilisateurs",
        description="Réservé à `super_admin` (écran Ministère \"Utilisateurs & droits d'accès\").",
    ),
    post=extend_schema(
        tags=[TAG_ACCOUNTS],
        summary="Créer un compte",
        description=(
            "Réservé à `super_admin`. `is_staff`/`is_superuser` ne sont "
            "pas des champs acceptés par cette route (accès `/admin/` "
            "uniquement, jamais accordable via l'API)."
        ),
        examples=[
            OpenApiExample(
                "Requête",
                value={
                    "email": "nouveau.biologiste@medirophe.test",
                    "first_name": "Awa",
                    "last_name": "Koné",
                    "role": "biologiste",
                    "password": "un-mot-de-passe-solide-42",
                },
                request_only=True,
            ),
        ],
    ),
)
class UserListView(generics.ListCreateAPIView):
    """Liste (écran Ministère "Utilisateurs & droits d'accès") et création de
    comptes — les deux réservées à `super_admin` via `permission_classes`.
    `get_queryset` renvoie tout le monde sans filtre : c'est correct ici
    puisque `super_admin` est censé voir/gérer tous les comptes, tous rôles
    confondus (contrairement à `UserDetailView`, où le filtrage se fait objet
    par objet via `IsSelfOrSuperAdmin`).
    """

    permission_classes = [IsSuperAdmin]

    def get_queryset(self):
        return User.objects.all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UserCreateSerializer
        return UserAdminSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        record(
            AuditAction.USER_CREATED,
            actor=self.request.user,
            target_user=user,
            request=self.request,
            role=user.role,
        )
