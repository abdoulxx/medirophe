import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.roles import Role
from apps.accounts.tests.factories import UserFactory
from apps.patients.models import Patient
from apps.patients.tests.factories import PatientFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


def authenticated_client(user):
    client = APIClient()
    access = str(RefreshToken.for_user(user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


# ---------------------------------------------------------------------------
# RBAC par rôle.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", [Role.MEDECIN, Role.BIOLOGISTE, Role.SUPER_ADMIN])
def test_clinique_staff_and_super_admin_can_list_patients(role):
    PatientFactory.create_batch(2)
    requester = UserFactory(role=role)
    client = authenticated_client(requester)

    response = client.get("/api/v1/patients/")

    assert response.status_code == 200
    assert response.data["count"] == 2


@pytest.mark.parametrize("role", [Role.ADMIN, Role.ANALYSTE])
def test_ministere_roles_cannot_access_patients(role):
    patient = PatientFactory()
    requester = UserFactory(role=role)
    client = authenticated_client(requester)

    list_response = client.get("/api/v1/patients/")
    detail_response = client.get(f"/api/v1/patients/{patient.pk}/")

    assert list_response.status_code == 403
    assert detail_response.status_code == 403


# ---------------------------------------------------------------------------
# Création / mass assignment.
# ---------------------------------------------------------------------------


def test_medecin_can_create_patient():
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/patients/",
        {
            "first_name": "Awa",
            "last_name": "Koné",
            "date_naissance": "1990-05-12",
            "sexe": "femme",
            "taille_cm": 170,
            "poids_kg": "68.0",
        },
        format="json",
    )

    assert response.status_code == 201
    patient = Patient.objects.get(pk=response.data["id"])
    assert patient.created_by == medecin
    assert patient.numero_dossier.startswith("MR-")
    assert response.data["imc"] == pytest.approx(23.5, abs=0.1)


def test_created_by_cannot_be_forced_via_payload():
    attacker = UserFactory(role=Role.MEDECIN)
    someone_else = UserFactory(role=Role.BIOLOGISTE)
    client = authenticated_client(attacker)

    response = client.post(
        "/api/v1/patients/",
        {
            "first_name": "Test",
            "last_name": "Mass-Assignment",
            "date_naissance": "2000-01-01",
            "sexe": "homme",
            "created_by": str(someone_else.pk),
        },
        format="json",
    )

    assert response.status_code == 201
    patient = Patient.objects.get(pk=response.data["id"])
    assert patient.created_by == attacker


def test_numero_dossier_cannot_be_forced_via_payload():
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/patients/",
        {
            "first_name": "Test",
            "last_name": "Dossier",
            "date_naissance": "2000-01-01",
            "sexe": "homme",
            "numero_dossier": "MR-FORCED1",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["numero_dossier"] != "MR-FORCED1"


# ---------------------------------------------------------------------------
# Recherche.
# ---------------------------------------------------------------------------


def test_search_filters_by_name():
    PatientFactory(first_name="Awa", last_name="Koné")
    PatientFactory(first_name="Ismael", last_name="Diallo")
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.get("/api/v1/patients/?search=koné")

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["last_name"] == "Koné"


def test_search_filters_by_numero_dossier():
    target = PatientFactory()
    PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.get(f"/api/v1/patients/?search={target.numero_dossier}")

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == str(target.pk)


@pytest.mark.parametrize("field,value", [("cni", "CNI-999"), ("telephone", "0708091011"), ("email", "zora@example.com")])
def test_search_filters_by_contact_fields(field, value):
    PatientFactory(**{field: value})
    PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.get(f"/api/v1/patients/?search={value}")

    assert response.status_code == 200
    assert response.data["count"] == 1


# ---------------------------------------------------------------------------
# Édition — accès partagé (pas de restriction par créateur).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Antécédents familiaux (sous-objet imbriqué, section 4 du formulaire).
# ---------------------------------------------------------------------------


def test_create_patient_with_antecedents_familiaux():
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/patients/",
        {
            "first_name": "Awa",
            "last_name": "Koné",
            "date_naissance": "1990-05-12",
            "sexe": "femme",
            "antecedents_familiaux": {
                "pere_vivant": True,
                "pere_age": 65,
                "pere_diabetique": False,
                "pere_pathologies": ["hypertension", "avc"],
                "mere_vivante": False,
                "autres_antecedents_familiaux": True,
            },
        },
        format="json",
    )

    assert response.status_code == 201
    patient = Patient.objects.get(pk=response.data["id"])
    assert patient.antecedents_familiaux.pere_age == 65
    assert patient.antecedents_familiaux.pere_pathologies == ["hypertension", "avc"]
    assert response.data["antecedents_familiaux"]["mere_vivante"] is False


def test_patient_without_antecedents_familiaux_returns_null():
    patient = PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.get(f"/api/v1/patients/{patient.pk}/")

    assert response.status_code == 200
    assert response.data["antecedents_familiaux"] is None


def test_invalid_pathologie_choice_rejected():
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/patients/",
        {
            "first_name": "Test",
            "last_name": "Invalide",
            "date_naissance": "2000-01-01",
            "sexe": "homme",
            "antecedents_familiaux": {"pere_pathologies": ["pathologie_inconnue"]},
        },
        format="json",
    )

    assert response.status_code == 400


def test_update_adds_antecedents_familiaux_to_existing_patient():
    patient = PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.patch(
        f"/api/v1/patients/{patient.pk}/",
        {"antecedents_familiaux": {"fratrie_vivant": True, "fratrie_age": 30}},
        format="json",
    )

    assert response.status_code == 200
    patient.refresh_from_db()
    assert patient.antecedents_familiaux.fratrie_age == 30


def test_any_clinique_staff_can_update_a_patient_created_by_someone_else():
    creator = UserFactory(role=Role.MEDECIN)
    patient = PatientFactory(created_by=creator)
    other_staff = UserFactory(role=Role.BIOLOGISTE)
    client = authenticated_client(other_staff)

    response = client.patch(
        f"/api/v1/patients/{patient.pk}/",
        {"telephone": "0102030405"},
        format="json",
    )

    assert response.status_code == 200
    patient.refresh_from_db()
    assert patient.telephone == "0102030405"


# ---------------------------------------------------------------------------
# Archivage (is_active) — réversible, ouvert à tout le personnel clinique.
# ---------------------------------------------------------------------------


def test_clinique_staff_can_archive_and_reactivate_a_patient():
    patient = PatientFactory()
    biologiste = UserFactory(role=Role.BIOLOGISTE)
    client = authenticated_client(biologiste)

    archive_response = client.patch(f"/api/v1/patients/{patient.pk}/", {"is_active": False}, format="json")
    assert archive_response.status_code == 200
    patient.refresh_from_db()
    assert patient.is_active is False

    reactivate_response = client.patch(f"/api/v1/patients/{patient.pk}/", {"is_active": True}, format="json")
    assert reactivate_response.status_code == 200
    patient.refresh_from_db()
    assert patient.is_active is True


def test_archiving_logs_patient_archived_action():
    from apps.audit.models import AuditAction, AuditLog

    patient = PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    client.patch(f"/api/v1/patients/{patient.pk}/", {"is_active": False}, format="json")

    assert AuditLog.objects.filter(action=AuditAction.PATIENT_ARCHIVED, metadata__patient_id=str(patient.pk)).exists()


# ---------------------------------------------------------------------------
# Suppression définitive — réservée à super_admin.
# ---------------------------------------------------------------------------


def test_super_admin_can_delete_a_patient():
    from apps.audit.models import AuditAction, AuditLog

    patient = PatientFactory()
    super_admin = UserFactory(role=Role.SUPER_ADMIN)
    client = authenticated_client(super_admin)

    response = client.delete(f"/api/v1/patients/{patient.pk}/")

    assert response.status_code == 204
    assert not Patient.objects.filter(pk=patient.pk).exists()
    assert AuditLog.objects.filter(action=AuditAction.PATIENT_DELETED, metadata__patient_id=str(patient.pk)).exists()


@pytest.mark.parametrize("role", [Role.MEDECIN, Role.BIOLOGISTE])
def test_clinique_staff_cannot_delete_a_patient(role):
    patient = PatientFactory()
    requester = UserFactory(role=role)
    client = authenticated_client(requester)

    response = client.delete(f"/api/v1/patients/{patient.pk}/")

    assert response.status_code == 403
    assert Patient.objects.filter(pk=patient.pk).exists()


# ---------------------------------------------------------------------------
# Durcissement sécurité — throttling, journalisation des lectures, validation.
# ---------------------------------------------------------------------------


def test_creating_patient_ignores_is_active_override():
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/patients/",
        {
            "first_name": "Test",
            "last_name": "Archive-A-La-Creation",
            "date_naissance": "2000-01-01",
            "sexe": "homme",
            "is_active": False,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["is_active"] is True


def test_future_date_naissance_rejected():
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/patients/",
        {"first_name": "Test", "last_name": "Futur", "date_naissance": "2999-01-01", "sexe": "homme"},
        format="json",
    )

    assert response.status_code == 400
    assert "date_naissance" in response.data


@pytest.mark.parametrize("field,value", [("taille_cm", 350), ("poids_kg", "600.0")])
def test_out_of_range_measurement_rejected(field, value):
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/patients/",
        {
            "first_name": "Test",
            "last_name": "Mesure",
            "date_naissance": "2000-01-01",
            "sexe": "homme",
            field: value,
        },
        format="json",
    )

    assert response.status_code == 400
    assert field in response.data


def test_retrieving_a_patient_logs_patient_viewed_action():
    from apps.audit.models import AuditAction, AuditLog

    patient = PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.get(f"/api/v1/patients/{patient.pk}/")

    assert response.status_code == 200
    assert AuditLog.objects.filter(action=AuditAction.PATIENT_VIEWED, metadata__patient_id=str(patient.pk)).exists()


def test_listing_patients_logs_patient_list_viewed_action():
    from apps.audit.models import AuditAction, AuditLog

    PatientFactory.create_batch(2)
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.get("/api/v1/patients/?search=")

    assert response.status_code == 200
    log = AuditLog.objects.filter(action=AuditAction.PATIENT_LIST_VIEWED).latest("created_at")
    assert log.metadata["result_count"] == 2


def test_updating_a_patient_logs_before_after_diff():
    from apps.audit.models import AuditAction, AuditLog

    patient = PatientFactory(telephone="0100000000")
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.patch(f"/api/v1/patients/{patient.pk}/", {"telephone": "0200000000"}, format="json")

    assert response.status_code == 200
    log = AuditLog.objects.filter(
        action=AuditAction.PATIENT_UPDATED, metadata__patient_id=str(patient.pk)
    ).latest("created_at")
    assert log.metadata["before"] == {"telephone": "0100000000"}
    assert log.metadata["after"] == {"telephone": "0200000000"}


def test_patients_list_endpoint_is_throttled(monkeypatch):
    # `THROTTLE_RATES` est un attribut de classe figé à l'import du module
    # (copie de `DEFAULT_THROTTLE_RATES`) — `override_settings`/le fixture
    # `settings` ne le rafraîchit pas, il faut le patcher directement.
    from apps.patients.throttling import PatientRateThrottle

    monkeypatch.setitem(PatientRateThrottle.THROTTLE_RATES, "patients", "2/min")
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    responses = [client.get("/api/v1/patients/") for _ in range(3)]

    assert [r.status_code for r in responses[:2]] == [200, 200]
    assert responses[2].status_code == 429
