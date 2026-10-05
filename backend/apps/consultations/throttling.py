from rest_framework.throttling import UserRateThrottle


class ConsultationRateThrottle(UserRateThrottle):
    """Même logique de menace que `apps.patients.throttling.PatientRateThrottle` :
    une consultation est un dossier partagé par l'équipe clinique (pas de
    restriction objet par créateur), donc ce throttle par utilisateur est le
    seul garde-fou contre un scraping en masse par un compte compromis. Taux
    dans `DEFAULT_THROTTLE_RATES["consultations"]`.
    """

    scope = "consultations"
