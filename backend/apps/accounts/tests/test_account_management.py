import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


def authenticated_client(user):
    client = APIClient()
    access = str(RefreshToken.for_user(user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    # Le throttle de login partage le cache Django entre tests ; sans reset,
    # un test peut être compté dans le quota d'un autre.
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# Création de compte (admin national uniquement).
# ---------------------------------------------------------------------------


def test_super_admin_can_create_user():
    admin = UserFactory(role=Role.SUPER_ADMIN)
    client = authenticated_client(admin)

    response = client.post(
        "/api/v1/accounts/users/",
        {
            "email": "nouveau@medirophe.test",
            "first_name": "Awa",
            "last_name": "Koné",
            "role": Role.BIOLOGISTE,
            "password": "Un-Mot-De-Passe-Solide-42",
        },
        format="json",
    )

    assert response.status_code == 201
    created = User.objects.get(email="nouveau@medirophe.test")
    assert created.role == Role.BIOLOGISTE
    assert created.check_password("Un-Mot-De-Passe-Solide-42")
    assert created.password.startswith("argon2$")


def test_non_admin_cannot_create_user():
    requester = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(requester)

    response = client.post(
        "/api/v1/accounts/users/",
        {
            "email": "intrus@medirophe.test",
            "role": Role.MEDECIN,
            "password": "Un-Mot-De-Passe-Solide-42",
        },
        format="json",
    )

    assert response.status_code == 403
    assert not User.objects.filter(email="intrus@medirophe.test").exists()


def test_created_user_cannot_be_granted_staff_or_superuser_via_extra_fields():
    admin = UserFactory(role=Role.SUPER_ADMIN)
    client = authenticated_client(admin)

    response = client.post(
        "/api/v1/accounts/users/",
        {
            "email": "test-mass-assignment@medirophe.test",
            "role": Role.MEDECIN,
            "password": "Un-Mot-De-Passe-Solide-42",
            "is_staff": True,
            "is_superuser": True,
        },
        format="json",
    )

    assert response.status_code == 201
    created = User.objects.get(email="test-mass-assignment@medirophe.test")
    assert created.is_staff is False
    assert created.is_superuser is False


def test_create_user_rejects_weak_password():
    admin = UserFactory(role=Role.SUPER_ADMIN)
    client = authenticated_client(admin)

    response = client.post(
        "/api/v1/accounts/users/",
        {"email": "faible@medirophe.test", "role": Role.MEDECIN, "password": "short"},
        format="json",
    )

    assert response.status_code == 400
    assert "password" in response.data
    assert not User.objects.filter(email="faible@medirophe.test").exists()


# ---------------------------------------------------------------------------
# Mise à jour d'un compte tiers (rôle / actif) — admin national uniquement.
# ---------------------------------------------------------------------------


def test_super_admin_can_update_role_and_is_active_of_another_user():
    target = UserFactory(role=Role.MEDECIN, is_active=True)
    admin = UserFactory(role=Role.SUPER_ADMIN)
    client = authenticated_client(admin)

    response = client.patch(
        f"/api/v1/accounts/users/{target.pk}/",
        {"role": Role.BIOLOGISTE, "is_active": False},
        format="json",
    )

    assert response.status_code == 200
    target.refresh_from_db()
    assert target.role == Role.BIOLOGISTE
    assert target.is_active is False


def test_non_admin_cannot_update_another_users_role():
    target = UserFactory(role=Role.MEDECIN)
    requester = UserFactory(role=Role.BIOLOGISTE)
    client = authenticated_client(requester)

    response = client.patch(
        f"/api/v1/accounts/users/{target.pk}/",
        {"role": Role.SUPER_ADMIN},
        format="json",
    )

    assert response.status_code == 403
    target.refresh_from_db()
    assert target.role == Role.MEDECIN


def test_user_cannot_self_promote_via_user_detail_endpoint():
    """La lecture de sa propre fiche via /users/<uuid>/ reste autorisée
    (self-or-admin), mais l'écriture est verrouillée admin-only : un
    utilisateur ne peut donc jamais s'auto-élever, même en visant son
    propre UUID sur cette route (seule /me/, en lecture seule sur `role`,
    est ouverte en écriture à self)."""
    user = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(user)

    response = client.patch(
        f"/api/v1/accounts/users/{user.pk}/",
        {"role": Role.SUPER_ADMIN},
        format="json",
    )

    assert response.status_code == 403
    user.refresh_from_db()
    assert user.role == Role.MEDECIN


# ---------------------------------------------------------------------------
# Suppression définitive (admin national uniquement).
# ---------------------------------------------------------------------------


def test_super_admin_can_delete_another_user():
    target = UserFactory(role=Role.MEDECIN)
    admin = UserFactory(role=Role.SUPER_ADMIN)
    client = authenticated_client(admin)

    response = client.delete(f"/api/v1/accounts/users/{target.pk}/")

    assert response.status_code == 204
    assert not User.objects.filter(pk=target.pk).exists()


def test_non_admin_cannot_delete_a_user():
    target = UserFactory(role=Role.MEDECIN)
    requester = UserFactory(role=Role.BIOLOGISTE)
    client = authenticated_client(requester)

    response = client.delete(f"/api/v1/accounts/users/{target.pk}/")

    assert response.status_code == 403
    assert User.objects.filter(pk=target.pk).exists()


def test_super_admin_cannot_delete_own_account():
    admin = UserFactory(role=Role.SUPER_ADMIN)
    client = authenticated_client(admin)

    response = client.delete(f"/api/v1/accounts/users/{admin.pk}/")

    assert response.status_code == 403
    assert User.objects.filter(pk=admin.pk).exists()


# ---------------------------------------------------------------------------
# Changement de mot de passe.
# ---------------------------------------------------------------------------


def test_change_password_success_revokes_existing_refresh_tokens():
    user = UserFactory()
    client = authenticated_client(user)
    old_refresh = RefreshToken.for_user(user)
    OutstandingToken.objects.get(jti=old_refresh["jti"])  # sanity: bien tracé

    response = client.post(
        "/api/v1/accounts/me/change-password/",
        {"old_password": DEFAULT_PASSWORD, "new_password": "Encore-Plus-Solide-77"},
        format="json",
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("Encore-Plus-Solide-77")

    outstanding = OutstandingToken.objects.get(jti=old_refresh["jti"])
    assert BlacklistedToken.objects.filter(token=outstanding).exists()

    replay = APIClient().post(
        "/api/v1/auth/token/refresh/", {"refresh": str(old_refresh)}, format="json"
    )
    assert replay.status_code == 401


def test_change_password_rejects_wrong_old_password():
    user = UserFactory()
    client = authenticated_client(user)

    response = client.post(
        "/api/v1/accounts/me/change-password/",
        {"old_password": "pas-le-bon-mot-de-passe", "new_password": "Encore-Plus-Solide-77"},
        format="json",
    )

    assert response.status_code == 400
    user.refresh_from_db()
    assert user.check_password(DEFAULT_PASSWORD)


def test_change_password_rejects_weak_new_password():
    user = UserFactory()
    client = authenticated_client(user)

    response = client.post(
        "/api/v1/accounts/me/change-password/",
        {"old_password": DEFAULT_PASSWORD, "new_password": "short"},
        format="json",
    )

    assert response.status_code == 400
    user.refresh_from_db()
    assert user.check_password(DEFAULT_PASSWORD)


# ---------------------------------------------------------------------------
# Freinage brute-force sur le login.
# ---------------------------------------------------------------------------


def test_login_endpoint_throttles_after_repeated_attempts():
    user = UserFactory()
    client = APIClient()

    responses = [
        client.post(
            "/api/v1/auth/token/",
            {"email": user.email, "password": "mauvais-mot-de-passe"},
            format="json",
        )
        for _ in range(6)
    ]

    assert [r.status_code for r in responses[:5]] == [401] * 5
    assert responses[5].status_code == 429
