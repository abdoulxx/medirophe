import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.roles import Role
from apps.accounts.tests.factories import UserFactory
from apps.audit.models import AuditAction, AuditLog
from apps.consultations.tests.factories import ConsultationFactory
from apps.patients.tests.factories import PatientFactory
from apps.prescriptions.models import Examen, Prescription
from apps.prescriptions.throttling import PrescriptionRateThrottle
from apps.prescriptions.tests.factories import ExamenFactory, PrescriptionFactory

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
# RBAC par rôle — lecture ET écriture ouvertes à médecin ET biologiste,
# contrairement à apps.consultations.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", [Role.MEDECIN, Role.BIOLOGISTE, Role.SUPER_ADMIN])
def test_clinique_staff_and_super_admin_can_list_prescriptions(role):
    PrescriptionFactory.create_batch(2)
    requester = UserFactory(role=role)
    client = authenticated_client(requester)

    response = client.get("/api/v1/prescriptions/")

    assert response.status_code == 200
    assert response.data["count"] == 2


@pytest.mark.parametrize("role", [Role.ADMIN, Role.ANALYSTE])
def test_ministere_roles_cannot_access_prescriptions(role):
    prescription = PrescriptionFactory()
    requester = UserFactory(role=role)
    client = authenticated_client(requester)

    list_response = client.get("/api/v1/prescriptions/")
    detail_response = client.get(f"/api/v1/prescriptions/{prescription.pk}/")

    assert list_response.status_code == 403
    assert detail_response.status_code == 403


@pytest.mark.parametrize("role", [Role.MEDECIN, Role.BIOLOGISTE])
def test_medecin_and_biologiste_can_create_prescription(role):
    patient = PatientFactory()
    examen = ExamenFactory()
    requester = UserFactory(role=role)
    client = authenticated_client(requester)

    response = client.post(
        "/api/v1/prescriptions/",
        {"patient": str(patient.pk), "motif": "Bilan", "examens_prescrits": [{"examen": str(examen.pk)}]},
        format="json",
    )

    assert response.status_code == 201
    prescription = Prescription.objects.get(pk=response.data["id"])
    assert prescription.cree_par == requester
    assert prescription.examens_prescrits.count() == 1


# ---------------------------------------------------------------------------
# Création / mass assignment / sous-ressources imbriquées / montant calculé.
# ---------------------------------------------------------------------------


def test_cree_par_cannot_be_forced_via_payload():
    attacker = UserFactory(role=Role.MEDECIN)
    someone_else = UserFactory(role=Role.MEDECIN)
    patient = PatientFactory()
    examen = ExamenFactory()
    client = authenticated_client(attacker)

    response = client.post(
        "/api/v1/prescriptions/",
        {
            "patient": str(patient.pk),
            "motif": "Bilan",
            "cree_par": str(someone_else.pk),
            "examens_prescrits": [{"examen": str(examen.pk)}],
        },
        format="json",
    )

    assert response.status_code == 201
    prescription = Prescription.objects.get(pk=response.data["id"])
    assert prescription.cree_par == attacker


def test_numero_demande_and_montant_are_server_computed():
    patient = PatientFactory()
    examen_a = ExamenFactory(prix_fcfa=3000)
    examen_b = ExamenFactory(prix_fcfa=4500)
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/prescriptions/",
        {
            "patient": str(patient.pk),
            "motif": "Bilan",
            "montant_fcfa": 999999,
            "numero_demande": "REQ-FORCED",
            "examens_prescrits": [{"examen": str(examen_a.pk)}, {"examen": str(examen_b.pk)}],
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["montant_fcfa"] == 7500
    assert response.data["numero_demande"] != "REQ-FORCED"
    assert response.data["numero_demande"].startswith("REQ-")


def test_empty_examens_prescrits_rejected():
    patient = PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/prescriptions/",
        {"patient": str(patient.pk), "motif": "Bilan", "examens_prescrits": []},
        format="json",
    )

    assert response.status_code == 400
    assert "examens_prescrits" in response.data


def test_duplicate_examen_in_same_request_rejected():
    patient = PatientFactory()
    examen = ExamenFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/prescriptions/",
        {
            "patient": str(patient.pk),
            "motif": "Bilan",
            "examens_prescrits": [{"examen": str(examen.pk)}, {"examen": str(examen.pk)}],
        },
        format="json",
    )

    assert response.status_code == 400
    assert "examens_prescrits" in response.data


def test_consultation_must_belong_to_same_patient():
    patient = PatientFactory()
    other_patient_consultation = ConsultationFactory()
    examen = ExamenFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/prescriptions/",
        {
            "patient": str(patient.pk),
            "consultation": str(other_patient_consultation.pk),
            "motif": "Bilan",
            "examens_prescrits": [{"examen": str(examen.pk)}],
        },
        format="json",
    )

    assert response.status_code == 400
    assert "consultation" in response.data


def test_consultation_matching_patient_is_accepted():
    patient = PatientFactory()
    consultation = ConsultationFactory(patient=patient)
    examen = ExamenFactory()
    biologiste = UserFactory(role=Role.BIOLOGISTE)
    client = authenticated_client(biologiste)

    response = client.post(
        "/api/v1/prescriptions/",
        {
            "patient": str(patient.pk),
            "consultation": str(consultation.pk),
            "motif": "Bilan",
            "examens_prescrits": [{"examen": str(examen.pk)}],
        },
        format="json",
    )

    assert response.status_code == 201


def test_couverture_requires_numero_when_not_aucune():
    patient = PatientFactory()
    examen = ExamenFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/prescriptions/",
        {
            "patient": str(patient.pk),
            "motif": "Bilan",
            "type_couverture": "cmu",
            "examens_prescrits": [{"examen": str(examen.pk)}],
        },
        format="json",
    )

    assert response.status_code == 400
    assert "numero_couverture" in response.data


def test_patient_and_consultation_cannot_be_changed_via_update():
    original_patient = PatientFactory()
    other_patient = PatientFactory()
    prescription = PrescriptionFactory(patient=original_patient)
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.patch(
        f"/api/v1/prescriptions/{prescription.pk}/",
        {"patient": str(other_patient.pk)},
        format="json",
    )

    assert response.status_code == 200
    prescription.refresh_from_db()
    assert prescription.patient == original_patient


def test_updating_examens_prescrits_replaces_existing_lines_and_recomputes_montant():
    prescription = PrescriptionFactory()
    old_examen = ExamenFactory(prix_fcfa=1000)
    prescription.examens_prescrits.create(examen=old_examen)
    prescription.recalculer_montant()
    new_examen = ExamenFactory(prix_fcfa=9000)
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.patch(
        f"/api/v1/prescriptions/{prescription.pk}/",
        {"examens_prescrits": [{"examen": str(new_examen.pk)}]},
        format="json",
    )

    assert response.status_code == 200
    prescription.refresh_from_db()
    assert prescription.examens_prescrits.count() == 1
    assert prescription.examens_prescrits.first().examen == new_examen
    assert prescription.montant_fcfa == 9000


# ---------------------------------------------------------------------------
# Statut, suppression, audit.
# ---------------------------------------------------------------------------


def test_only_super_admin_can_delete_prescription():
    prescription = PrescriptionFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.delete(f"/api/v1/prescriptions/{prescription.pk}/")

    assert response.status_code == 403
    assert Prescription.objects.filter(pk=prescription.pk).exists()


def test_setting_statut_to_valide_logs_dedicated_audit_action():
    prescription = PrescriptionFactory()
    biologiste = UserFactory(role=Role.BIOLOGISTE)
    client = authenticated_client(biologiste)

    response = client.patch(f"/api/v1/prescriptions/{prescription.pk}/", {"statut": "valide"}, format="json")

    assert response.status_code == 200
    assert AuditLog.objects.filter(action=AuditAction.PRESCRIPTION_EXAMEN_VALIDEE).exists()


def test_setting_statut_to_rejete_logs_dedicated_audit_action():
    prescription = PrescriptionFactory()
    biologiste = UserFactory(role=Role.BIOLOGISTE)
    client = authenticated_client(biologiste)

    response = client.patch(f"/api/v1/prescriptions/{prescription.pk}/", {"statut": "rejete"}, format="json")

    assert response.status_code == 200
    assert AuditLog.objects.filter(action=AuditAction.PRESCRIPTION_EXAMEN_REJETEE).exists()


def test_retrieving_a_prescription_logs_prescription_viewed_action():
    prescription = PrescriptionFactory()
    requester = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(requester)

    response = client.get(f"/api/v1/prescriptions/{prescription.pk}/")

    assert response.status_code == 200
    assert AuditLog.objects.filter(action=AuditAction.PRESCRIPTION_EXAMEN_VIEWED).exists()


def test_prescriptions_list_endpoint_is_throttled(monkeypatch):
    monkeypatch.setitem(PrescriptionRateThrottle.THROTTLE_RATES, "prescriptions", "2/min")
    PrescriptionFactory()
    requester = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(requester)

    responses = [client.get("/api/v1/prescriptions/") for _ in range(3)]

    assert [r.status_code for r in responses[:2]] == [200, 200]
    assert responses[2].status_code == 429


# ---------------------------------------------------------------------------
# Référentiel des examens (`GET /api/v1/prescriptions/examens/`).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", [Role.MEDECIN, Role.BIOLOGISTE, Role.SUPER_ADMIN])
def test_clinique_staff_and_super_admin_can_list_examens(role):
    # Le catalogue est déjà peuplé par la migration de seed (103 examens) —
    # on vérifie l'incrément plutôt qu'un total absolu.
    before = Examen.objects.count()
    ExamenFactory.create_batch(3)
    requester = UserFactory(role=role)
    client = authenticated_client(requester)

    response = client.get("/api/v1/prescriptions/examens/")

    assert response.status_code == 200
    assert len(response.data) == before + 3


@pytest.mark.parametrize("role", [Role.ADMIN, Role.ANALYSTE])
def test_ministere_roles_cannot_list_examens(role):
    requester = UserFactory(role=role)
    client = authenticated_client(requester)

    response = client.get("/api/v1/prescriptions/examens/")

    assert response.status_code == 403


def test_examen_list_endpoint_is_read_only():
    requester = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(requester)

    response = client.post(
        "/api/v1/prescriptions/examens/",
        {"code": "NEW-01", "nom": "Nouvel examen", "categorie": "metabolisme", "taux_cmu": 50, "prix_fcfa": 1000},
        format="json",
    )

    assert response.status_code == 405
    assert not Examen.objects.filter(code="NEW-01").exists()


def test_examen_list_can_be_filtered_by_categorie_and_search():
    ExamenFactory(nom="Recherche spécifique", categorie="toxicologie")
    requester = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(requester)

    response = client.get("/api/v1/prescriptions/examens/?categorie=toxicologie&search=spécifique")

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["nom"] == "Recherche spécifique"
