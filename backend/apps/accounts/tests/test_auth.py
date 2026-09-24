import pytest
from django.contrib.auth.hashers import Argon2PasswordHasher
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


def test_password_is_hashed_with_argon2():
    user = UserFactory()
    assert user.password.startswith("argon2$")
    # Sanity check: le hasher configuré en premier est bien Argon2.
    assert isinstance(Argon2PasswordHasher(), Argon2PasswordHasher)


def test_login_success_returns_access_and_refresh_with_role_claim():
    user = UserFactory(role=Role.MEDECIN)
    client = APIClient()

    response = client.post(
        "/api/v1/auth/token/",
        {"email": user.email, "password": DEFAULT_PASSWORD},
        format="json",
    )

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


def test_login_wrong_password_and_unknown_email_return_identical_generic_error():
    """Message d'erreur non énumératif : on ne doit pas pouvoir distinguer
    "email inconnu" de "mot de passe incorrect" (évite l'énumération de
    comptes existants)."""
    user = UserFactory()
    client = APIClient()

    wrong_password_resp = client.post(
        "/api/v1/auth/token/",
        {"email": user.email, "password": "not-the-password"},
        format="json",
    )
    unknown_email_resp = client.post(
        "/api/v1/auth/token/",
        {"email": "does-not-exist@medirophe.test", "password": "whatever"},
        format="json",
    )

    assert wrong_password_resp.status_code == 401
    assert unknown_email_resp.status_code == 401
    assert wrong_password_resp.data == unknown_email_resp.data


def test_inactive_user_cannot_login():
    user = UserFactory(is_active=False)
    client = APIClient()

    response = client.post(
        "/api/v1/auth/token/",
        {"email": user.email, "password": DEFAULT_PASSWORD},
        format="json",
    )

    assert response.status_code == 401


def test_unauthenticated_request_is_denied_on_protected_endpoint():
    client = APIClient()
    response = client.get("/api/v1/accounts/me/")
    assert response.status_code == 401


def test_refresh_token_rotation_blacklists_the_old_refresh_token():
    """BLACKLIST_AFTER_ROTATION=True : après un refresh, l'ancien refresh
    token ne doit plus jamais fonctionner (protection contre le rejeu d'un
    token volé après qu'il a déjà servi une fois)."""
    user = UserFactory()
    client = APIClient()

    login = client.post(
        "/api/v1/auth/token/",
        {"email": user.email, "password": DEFAULT_PASSWORD},
        format="json",
    )
    old_refresh = login.data["refresh"]

    first_use = client.post("/api/v1/auth/token/refresh/", {"refresh": old_refresh}, format="json")
    assert first_use.status_code == 200
    assert "access" in first_use.data

    replay = client.post("/api/v1/auth/token/refresh/", {"refresh": old_refresh}, format="json")
    assert replay.status_code == 401
