import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.roles import Role
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def authenticated_client(user):
    client = APIClient()
    access = str(RefreshToken.for_user(user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


# ---------------------------------------------------------------------------
# Mass assignment (section 3 : "jamais fields = '__all__'", pas d'auto
# élévation de privilèges via un PATCH sur son propre profil).
# ---------------------------------------------------------------------------

def test_user_cannot_self_escalate_role_via_me_endpoint():
    user = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(user)

    response = client.patch(
        "/api/v1/accounts/me/",
        {"role": Role.SUPER_ADMIN, "is_active": False, "first_name": "Nouveau"},
        format="json",
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.role == Role.MEDECIN  # inchangé malgré la tentative
    assert user.is_active is True  # inchangé malgré la tentative
    assert user.first_name == "Nouveau"  # les champs autorisés restent modifiables


# ---------------------------------------------------------------------------
# IDOR / BOLA : accès croisé entre deux comptes du même rôle.
# ---------------------------------------------------------------------------

def test_user_cannot_read_another_users_detail():
    victim = UserFactory(role=Role.MEDECIN)
    attacker = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(attacker)

    response = client.get(f"/api/v1/accounts/users/{victim.pk}/")

    assert response.status_code == 403


def test_user_can_read_own_detail_via_users_endpoint():
    user = UserFactory(role=Role.BIOLOGISTE)
    client = authenticated_client(user)

    response = client.get(f"/api/v1/accounts/users/{user.pk}/")

    assert response.status_code == 200
    assert response.data["id"] == str(user.pk)


def test_super_admin_can_read_any_users_detail():
    other = UserFactory(role=Role.BIOLOGISTE)
    admin = UserFactory(role=Role.SUPER_ADMIN)
    client = authenticated_client(admin)

    response = client.get(f"/api/v1/accounts/users/{other.pk}/")

    assert response.status_code == 200
    assert response.data["id"] == str(other.pk)


# ---------------------------------------------------------------------------
# RBAC par rôle sur l'écran Ministère "Utilisateurs & droits d'accès".
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "role",
    [Role.MEDECIN, Role.BIOLOGISTE, Role.ANALYSTE, Role.ADMIN],
)
def test_only_super_admin_can_list_all_users(role):
    UserFactory()  # au moins un autre utilisateur à "fuiter" si la faille existait
    requester = UserFactory(role=role)
    client = authenticated_client(requester)

    response = client.get("/api/v1/accounts/users/")

    assert response.status_code == 403


def test_super_admin_can_list_all_users():
    UserFactory.create_batch(3)
    admin = UserFactory(role=Role.SUPER_ADMIN)
    client = authenticated_client(admin)

    response = client.get("/api/v1/accounts/users/")

    assert response.status_code == 200
    assert response.data["count"] >= 4  # les 3 créés + l'admin lui-même
