import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.roles import Role
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory
from apps.audit.models import AuditAction, AuditLog

pytestmark = pytest.mark.django_db


def authenticated_client(user):
    client = APIClient()
    access = str(RefreshToken.for_user(user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# Événements journalisés automatiquement par les vues accounts.
# ---------------------------------------------------------------------------


def test_successful_login_is_logged_with_actor():
    user = UserFactory()
    client = APIClient()

    response = client.post(
        "/api/v1/auth/token/", {"email": user.email, "password": DEFAULT_PASSWORD}, format="json"
    )

    assert response.status_code == 200
    entry = AuditLog.objects.get(action=AuditAction.LOGIN_SUCCESS)
    assert entry.actor == user
    assert entry.actor_email == user.email


def test_failed_login_is_logged_without_actor():
    client = APIClient()

    response = client.post(
        "/api/v1/auth/token/", {"email": "inconnu@medirophe.test", "password": "n-importe-quoi"}, format="json"
    )

    assert response.status_code == 401
    entry = AuditLog.objects.get(action=AuditAction.LOGIN_FAILED)
    assert entry.actor is None
    assert entry.actor_email == "inconnu@medirophe.test"


def test_logout_is_logged_with_actor():
    user = UserFactory()
    refresh = RefreshToken.for_user(user)
    client = APIClient()

    response = client.post("/api/v1/auth/token/blacklist/", {"refresh": str(refresh)}, format="json")

    assert response.status_code == 200
    entry = AuditLog.objects.get(action=AuditAction.LOGOUT)
    assert entry.actor == user


def test_change_password_is_logged():
    user = UserFactory()
    client = authenticated_client(user)

    response = client.post(
        "/api/v1/accounts/me/change-password/",
        {"old_password": DEFAULT_PASSWORD, "new_password": "Encore-Plus-Solide-77"},
        format="json",
    )

    assert response.status_code == 200
    entry = AuditLog.objects.get(action=AuditAction.PASSWORD_CHANGED)
    assert entry.actor == user
    assert entry.target_user == user


def test_password_reset_request_is_logged_for_known_and_unknown_email():
    user = UserFactory()
    client = APIClient()

    client.post("/api/v1/auth/password-reset/", {"email": user.email}, format="json")
    client.post("/api/v1/auth/password-reset/", {"email": "inconnu@medirophe.test"}, format="json")

    entries = AuditLog.objects.filter(action=AuditAction.PASSWORD_RESET_REQUESTED).order_by("created_at")
    assert entries.count() == 2
    assert entries[0].target_user == user
    assert entries[1].target_user is None
    assert entries[1].metadata.get("account_found") is False


def test_user_creation_is_logged():
    admin = UserFactory(role=Role.SUPER_ADMIN)
    client = authenticated_client(admin)

    response = client.post(
        "/api/v1/accounts/users/",
        {
            "email": "nouveau@medirophe.test",
            "role": Role.BIOLOGISTE,
            "password": "Un-Mot-De-Passe-Solide-42",
        },
        format="json",
    )

    assert response.status_code == 201
    entry = AuditLog.objects.get(action=AuditAction.USER_CREATED)
    assert entry.actor == admin
    assert entry.target_user_email == "nouveau@medirophe.test"


def test_user_deletion_is_logged_and_target_user_is_nulled_but_email_kept():
    target = UserFactory(role=Role.MEDECIN)
    target_pk = target.pk
    target_email = target.email
    admin = UserFactory(role=Role.SUPER_ADMIN)
    client = authenticated_client(admin)

    response = client.delete(f"/api/v1/accounts/users/{target_pk}/")

    assert response.status_code == 204
    entry = AuditLog.objects.get(action=AuditAction.USER_DELETED)
    assert entry.actor == admin
    assert entry.target_user is None
    assert entry.target_user_email == target_email


def test_user_role_update_is_logged_with_before_after():
    target = UserFactory(role=Role.MEDECIN, is_active=True)
    admin = UserFactory(role=Role.SUPER_ADMIN)
    client = authenticated_client(admin)

    response = client.patch(
        f"/api/v1/accounts/users/{target.pk}/", {"role": Role.BIOLOGISTE}, format="json"
    )

    assert response.status_code == 200
    entry = AuditLog.objects.get(action=AuditAction.USER_UPDATED)
    assert entry.actor == admin
    assert entry.target_user == target
    assert entry.metadata["before"]["role"] == Role.MEDECIN
    assert entry.metadata["after"]["role"] == Role.BIOLOGISTE


# ---------------------------------------------------------------------------
# Immuabilité du modèle.
# ---------------------------------------------------------------------------


def test_audit_log_cannot_be_modified_after_creation():
    entry = AuditLog.objects.create(action=AuditAction.LOGIN_SUCCESS, actor_email="a@medirophe.test")

    entry.actor_email = "modifie@medirophe.test"
    with pytest.raises(ValueError):
        entry.save()


def test_audit_log_cannot_be_deleted():
    entry = AuditLog.objects.create(action=AuditAction.LOGIN_SUCCESS, actor_email="a@medirophe.test")

    with pytest.raises(ValueError):
        entry.delete()


# ---------------------------------------------------------------------------
# API de lecture — réservée à super_admin.
# ---------------------------------------------------------------------------


def test_super_admin_can_list_audit_logs():
    AuditLog.objects.create(action=AuditAction.LOGIN_SUCCESS, actor_email="a@medirophe.test")
    admin = UserFactory(role=Role.SUPER_ADMIN)
    client = authenticated_client(admin)

    response = client.get("/api/v1/audit/logs/")

    assert response.status_code == 200
    assert response.data["count"] >= 1


def test_non_admin_cannot_list_audit_logs():
    requester = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(requester)

    response = client.get("/api/v1/audit/logs/")

    assert response.status_code == 403


def test_audit_logs_can_be_filtered_by_action():
    AuditLog.objects.create(action=AuditAction.LOGIN_SUCCESS, actor_email="a@medirophe.test")
    AuditLog.objects.create(action=AuditAction.LOGIN_FAILED, actor_email="b@medirophe.test")
    admin = UserFactory(role=Role.SUPER_ADMIN)
    client = authenticated_client(admin)

    response = client.get("/api/v1/audit/logs/", {"action": AuditAction.LOGIN_FAILED})

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["action"] == AuditAction.LOGIN_FAILED
