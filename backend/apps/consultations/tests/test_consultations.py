import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.roles import Role
from apps.accounts.tests.factories import UserFactory
from apps.audit.models import AuditAction, AuditLog
from apps.consultations.models import Consultation, Service
from apps.consultations.throttling import ConsultationRateThrottle
from apps.consultations.tests.factories import ConsultationFactory, ServiceFactory
from apps.patients.models import Sexe
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
def test_clinique_staff_and_super_admin_can_list_consultations(role):
    ConsultationFactory.create_batch(2)
    requester = UserFactory(role=role)
    client = authenticated_client(requester)

    response = client.get("/api/v1/consultations/")

    assert response.status_code == 200
    assert response.data["count"] == 2


@pytest.mark.parametrize("role", [Role.ADMIN, Role.ANALYSTE])
def test_ministere_roles_cannot_access_consultations(role):
    consultation = ConsultationFactory()
    requester = UserFactory(role=role)
    client = authenticated_client(requester)

    list_response = client.get("/api/v1/consultations/")
    detail_response = client.get(f"/api/v1/consultations/{consultation.pk}/")

    assert list_response.status_code == 403
    assert detail_response.status_code == 403


def test_biologiste_can_read_but_not_create_consultation():
    patient = PatientFactory()
    biologiste = UserFactory(role=Role.BIOLOGISTE)
    client = authenticated_client(biologiste)

    response = client.post(
        "/api/v1/consultations/", {"patient": str(patient.pk), "motif": "Fièvre"}, format="json"
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Création / mass assignment / sous-ressources imbriquées.
# ---------------------------------------------------------------------------


def test_medecin_can_create_consultation_with_nested_prescriptions_and_rdv():
    patient = PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/consultations/",
        {
            "patient": str(patient.pk),
            "motif": "Douleur thoracique",
            "type_consultation": "urgence",
            "poids_kg": "70.0",
            "taille_cm": 175,
            "symptomes": [{"label": "fievre", "duree": "2 jours"}],
            "prescriptions": [{"medicament": "Paracétamol", "posologie": "1g x3/j", "duree": "5 jours"}],
            "rendez_vous_suivi": [{"date_rdv": "2026-11-01", "motif": "Contrôle"}],
            "conseils_patient": [{"label": "repos", "texte": "Repos pendant 48h"}],
        },
        format="json",
    )

    assert response.status_code == 201
    consultation = Consultation.objects.get(pk=response.data["id"])
    assert consultation.medecin == medecin
    assert consultation.prescriptions.count() == 1
    assert consultation.rendez_vous_suivi.count() == 1
    assert consultation.conseils_patient.count() == 1
    assert response.data["imc"] == pytest.approx(22.9, abs=0.1)


def test_medecin_cannot_be_forced_via_payload():
    attacker = UserFactory(role=Role.MEDECIN)
    someone_else = UserFactory(role=Role.MEDECIN)
    patient = PatientFactory()
    client = authenticated_client(attacker)

    response = client.post(
        "/api/v1/consultations/",
        {"patient": str(patient.pk), "motif": "Suivi", "medecin": str(someone_else.pk)},
        format="json",
    )

    assert response.status_code == 201
    consultation = Consultation.objects.get(pk=response.data["id"])
    assert consultation.medecin == attacker


def test_patient_cannot_be_changed_via_update():
    original_patient = PatientFactory()
    other_patient = PatientFactory()
    consultation = ConsultationFactory(patient=original_patient)
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.patch(
        f"/api/v1/consultations/{consultation.pk}/",
        {"patient": str(other_patient.pk)},
        format="json",
    )

    assert response.status_code == 200
    consultation.refresh_from_db()
    assert consultation.patient == original_patient


# ---------------------------------------------------------------------------
# Validation métier.
# ---------------------------------------------------------------------------


def test_grossesse_trimestre_requires_grossesse_en_cours():
    patient = PatientFactory(sexe=Sexe.FEMME)
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/consultations/",
        {"patient": str(patient.pk), "motif": "Suivi", "grossesse_trimestre": 2},
        format="json",
    )

    assert response.status_code == 400
    assert "grossesse_trimestre" in response.data


def test_grossesse_en_cours_rejected_for_male_patient():
    patient = PatientFactory(sexe=Sexe.HOMME)
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/consultations/",
        {"patient": str(patient.pk), "motif": "Suivi", "grossesse_en_cours": True},
        format="json",
    )

    assert response.status_code == 400
    assert "grossesse_en_cours" in response.data


@pytest.mark.parametrize("field,value", [("frequence_cardiaque", 500), ("spo2", 150), ("taille_cm", 400)])
def test_out_of_range_vitals_rejected(field, value):
    patient = PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/consultations/", {"patient": str(patient.pk), "motif": "Suivi", field: value}, format="json"
    )

    assert response.status_code == 400
    assert field in response.data


def test_symptomes_must_be_list_of_objects_with_label():
    patient = PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/consultations/",
        {"patient": str(patient.pk), "motif": "Suivi", "symptomes": ["fievre"]},
        format="json",
    )

    assert response.status_code == 400
    assert "symptomes" in response.data


# ---------------------------------------------------------------------------
# Mise à jour, statut, suppression, audit.
# ---------------------------------------------------------------------------


def test_updating_prescriptions_replaces_existing_lines():
    consultation = ConsultationFactory()
    consultation.prescriptions.create(medicament="Ancien médicament")
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.patch(
        f"/api/v1/consultations/{consultation.pk}/",
        {"prescriptions": [{"medicament": "Nouveau médicament"}]},
        format="json",
    )

    assert response.status_code == 200
    consultation.refresh_from_db()
    assert consultation.prescriptions.count() == 1
    assert consultation.prescriptions.first().medicament == "Nouveau médicament"


def test_updating_conseils_patient_replaces_existing_lines():
    consultation = ConsultationFactory()
    consultation.conseils_patient.create(label="ancien-conseil", texte="Ancien texte")
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.patch(
        f"/api/v1/consultations/{consultation.pk}/",
        {"conseils_patient": [{"label": "hydratation", "texte": "Boire 1,5L d'eau par jour"}]},
        format="json",
    )

    assert response.status_code == 200
    consultation.refresh_from_db()
    assert consultation.conseils_patient.count() == 1
    assert consultation.conseils_patient.first().label == "hydratation"


def test_biologiste_cannot_update_consultation():
    consultation = ConsultationFactory()
    biologiste = UserFactory(role=Role.BIOLOGISTE)
    client = authenticated_client(biologiste)

    response = client.patch(f"/api/v1/consultations/{consultation.pk}/", {"statut": "terminee"}, format="json")

    assert response.status_code == 403


def test_only_super_admin_can_delete_consultation():
    consultation = ConsultationFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.delete(f"/api/v1/consultations/{consultation.pk}/")

    assert response.status_code == 403
    assert Consultation.objects.filter(pk=consultation.pk).exists()


def test_setting_statut_to_terminee_logs_dedicated_audit_action():
    consultation = ConsultationFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.patch(f"/api/v1/consultations/{consultation.pk}/", {"statut": "terminee"}, format="json")

    assert response.status_code == 200
    assert AuditLog.objects.filter(action=AuditAction.CONSULTATION_TERMINEE).exists()


def test_retrieving_a_consultation_logs_consultation_viewed_action():
    consultation = ConsultationFactory()
    requester = UserFactory(role=Role.BIOLOGISTE)
    client = authenticated_client(requester)

    response = client.get(f"/api/v1/consultations/{consultation.pk}/")

    assert response.status_code == 200
    assert AuditLog.objects.filter(action=AuditAction.CONSULTATION_VIEWED).exists()


def test_consultations_list_endpoint_is_throttled(monkeypatch):
    monkeypatch.setitem(ConsultationRateThrottle.THROTTLE_RATES, "consultations", "2/min")
    ConsultationFactory()
    requester = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(requester)

    responses = [client.get("/api/v1/consultations/") for _ in range(3)]

    assert [r.status_code for r in responses[:2]] == [200, 200]
    assert responses[2].status_code == 429


# ---------------------------------------------------------------------------
# Admission & pré-consultation (couverture, orientation, médecin orienté,
# urgence, motif_categories) — étape du prototype ajoutée après coup, voir
# CLAUDE.md "Admission & Pré-consultation".
# ---------------------------------------------------------------------------


def test_couverture_requires_numero_when_not_aucune():
    patient = PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/consultations/",
        {"patient": str(patient.pk), "motif": "Suivi", "type_couverture": "cmu"},
        format="json",
    )

    assert response.status_code == 400
    assert "numero_couverture" in response.data


def test_couverture_with_numero_is_accepted():
    patient = PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/consultations/",
        {
            "patient": str(patient.pk),
            "motif": "Suivi",
            "type_couverture": "mutuelle",
            "numero_couverture": "MUT-12345",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["numero_couverture"] == "MUT-12345"


def test_motif_categories_rejects_unknown_value():
    patient = PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/consultations/",
        {"patient": str(patient.pk), "motif": "Suivi", "motif_categories": ["valeur_inconnue"]},
        format="json",
    )

    assert response.status_code == 400
    assert "motif_categories" in response.data


def test_motif_categories_accepts_known_values():
    patient = PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/consultations/",
        {
            "patient": str(patient.pk),
            "motif": "Suivi",
            "motif_categories": ["urgences", "pediatrie"],
        },
        format="json",
    )

    assert response.status_code == 201
    assert sorted(response.data["motif_categories"]) == ["pediatrie", "urgences"]


def test_medecin_oriente_must_have_medecin_role():
    patient = PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    biologiste = UserFactory(role=Role.BIOLOGISTE)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/consultations/",
        {"patient": str(patient.pk), "motif": "Suivi", "medecin_oriente": str(biologiste.pk)},
        format="json",
    )

    assert response.status_code == 400
    assert "medecin_oriente" in response.data


def test_medecin_oriente_accepted_when_role_is_medecin():
    patient = PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    autre_medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/consultations/",
        {"patient": str(patient.pk), "motif": "Suivi", "medecin_oriente": str(autre_medecin.pk)},
        format="json",
    )

    assert response.status_code == 201
    consultation = Consultation.objects.get(pk=response.data["id"])
    assert consultation.medecin_oriente == autre_medecin
    # Contrairement à `medecin`, `medecin_oriente` est bien client-writable.
    assert consultation.medecin == medecin


def test_services_orientation_set_on_create_and_detail_is_nested():
    patient = PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    service_a = ServiceFactory()
    service_b = ServiceFactory()
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/consultations/",
        {
            "patient": str(patient.pk),
            "motif": "Suivi",
            "services_orientation": [str(service_a.pk), str(service_b.pk)],
        },
        format="json",
    )

    assert response.status_code == 201
    consultation = Consultation.objects.get(pk=response.data["id"])
    assert consultation.services_orientation.count() == 2
    detail_ids = {item["id"] for item in response.data["services_orientation_detail"]}
    assert detail_ids == {str(service_a.pk), str(service_b.pk)}


def test_services_orientation_update_replaces_selection():
    consultation = ConsultationFactory()
    service_a = ServiceFactory()
    service_b = ServiceFactory()
    consultation.services_orientation.set([service_a])
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.patch(
        f"/api/v1/consultations/{consultation.pk}/",
        {"services_orientation": [str(service_b.pk)]},
        format="json",
    )

    assert response.status_code == 200
    consultation.refresh_from_db()
    assert list(consultation.services_orientation.all()) == [service_b]


def test_updating_services_orientation_does_not_create_false_positive_audit_diff():
    consultation = ConsultationFactory()
    service_a = ServiceFactory()
    consultation.services_orientation.set([service_a])
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.patch(
        f"/api/v1/consultations/{consultation.pk}/",
        {"services_orientation": [str(service_a.pk)]},
        format="json",
    )

    assert response.status_code == 200
    log = AuditLog.objects.filter(action=AuditAction.CONSULTATION_UPDATED).latest("created_at")
    assert "services_orientation" not in log.metadata.get("before", {})
    assert "services_orientation" not in log.metadata.get("after", {})


def test_urgence_flag_is_persisted():
    patient = PatientFactory()
    medecin = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(medecin)

    response = client.post(
        "/api/v1/consultations/",
        {"patient": str(patient.pk), "motif": "Suivi", "urgence": True},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["urgence"] is True


# ---------------------------------------------------------------------------
# Référentiel des services d'orientation (`GET /api/v1/consultations/services/`).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", [Role.MEDECIN, Role.BIOLOGISTE, Role.SUPER_ADMIN])
def test_clinique_staff_and_super_admin_can_list_services(role):
    # Le catalogue est déjà peuplé par la migration de seed (47 services) —
    # on vérifie l'incrément plutôt qu'un total absolu.
    before = Service.objects.count()
    ServiceFactory.create_batch(3)
    requester = UserFactory(role=role)
    client = authenticated_client(requester)

    response = client.get("/api/v1/consultations/services/")

    assert response.status_code == 200
    assert len(response.data) == before + 3


@pytest.mark.parametrize("role", [Role.ADMIN, Role.ANALYSTE])
def test_ministere_roles_cannot_list_services(role):
    requester = UserFactory(role=role)
    client = authenticated_client(requester)

    response = client.get("/api/v1/consultations/services/")

    assert response.status_code == 403


def test_service_list_endpoint_is_read_only():
    requester = UserFactory(role=Role.MEDECIN)
    client = authenticated_client(requester)

    response = client.post(
        "/api/v1/consultations/services/", {"categorie": "clinique", "nom": "Nouveau service"}, format="json"
    )

    assert response.status_code == 405
    assert not Service.objects.filter(nom="Nouveau service").exists()
