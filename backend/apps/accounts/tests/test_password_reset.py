import pytest
from django.core import mail
from django.core.cache import cache
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.password_reset import token_generator
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


def _uid_for(user):
    return urlsafe_base64_encode(force_bytes(str(user.pk)))


def test_password_reset_request_sends_email_for_existing_active_user():
    user = UserFactory()
    client = APIClient()

    response = client.post("/api/v1/auth/password-reset/", {"email": user.email}, format="json")

    assert response.status_code == 200
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [user.email]


def test_password_reset_request_is_silent_and_non_enumerable_for_unknown_email():
    client = APIClient()

    response = client.post(
        "/api/v1/auth/password-reset/", {"email": "inconnu@medirophe.test"}, format="json"
    )

    assert response.status_code == 200
    assert len(mail.outbox) == 0


def test_password_reset_request_is_silent_for_inactive_user():
    user = UserFactory(is_active=False)
    client = APIClient()

    response = client.post("/api/v1/auth/password-reset/", {"email": user.email}, format="json")

    assert response.status_code == 200
    assert len(mail.outbox) == 0


def test_password_reset_confirm_success_changes_password_and_revokes_tokens():
    user = UserFactory()
    old_refresh = RefreshToken.for_user(user)
    token = token_generator.make_token(user)
    client = APIClient()

    response = client.post(
        "/api/v1/auth/password-reset/confirm/",
        {"uid": _uid_for(user), "token": token, "new_password": "Nouveau-Mot-De-Passe-99"},
        format="json",
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("Nouveau-Mot-De-Passe-99")

    replay = client.post("/api/v1/auth/token/refresh/", {"refresh": str(old_refresh)}, format="json")
    assert replay.status_code == 401


def test_password_reset_confirm_rejects_invalid_token():
    user = UserFactory()
    client = APIClient()

    response = client.post(
        "/api/v1/auth/password-reset/confirm/",
        {"uid": _uid_for(user), "token": "token-invalide", "new_password": "Nouveau-Mot-De-Passe-99"},
        format="json",
    )

    assert response.status_code == 400
    user.refresh_from_db()
    assert user.check_password(DEFAULT_PASSWORD)


def test_password_reset_confirm_rejects_token_after_password_already_changed():
    """Un token de reset ne doit servir qu'une fois : dès que le mot de passe
    change (ici via un premier reset), le hash utilisé par
    PasswordResetTokenGenerator change aussi, donc tout token émis avant
    devient automatiquement invalide — y compris s'il n'a jamais servi."""
    user = UserFactory()
    token = token_generator.make_token(user)
    client = APIClient()

    user.set_password("Un-Autre-Mot-De-Passe-77")
    user.save(update_fields=["password"])

    response = client.post(
        "/api/v1/auth/password-reset/confirm/",
        {"uid": _uid_for(user), "token": token, "new_password": "Encore-Un-Autre-88"},
        format="json",
    )

    assert response.status_code == 400


def test_password_reset_confirm_rejects_weak_new_password():
    user = UserFactory()
    token = token_generator.make_token(user)
    client = APIClient()

    response = client.post(
        "/api/v1/auth/password-reset/confirm/",
        {"uid": _uid_for(user), "token": token, "new_password": "short"},
        format="json",
    )

    assert response.status_code == 400
    user.refresh_from_db()
    assert user.check_password(DEFAULT_PASSWORD)


def test_password_reset_request_is_throttled():
    client = APIClient()

    responses = [
        client.post("/api/v1/auth/password-reset/", {"email": "x@medirophe.test"}, format="json")
        for _ in range(4)
    ]

    assert [r.status_code for r in responses[:3]] == [200] * 3
    assert responses[3].status_code == 429
