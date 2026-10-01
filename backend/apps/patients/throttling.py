from rest_framework.throttling import UserRateThrottle


class PatientRateThrottle(UserRateThrottle):
    """Limite l'accès aux endpoints patients par utilisateur authentifié.

    Contrairement à `accounts` (throttle par IP sur login/reset, non
    authentifié), ici l'attaquant potentiel est un compte clinique légitime
    compromis ou malveillant : sans restriction objet sur `Patient` (voir
    `permissions.py`), ce throttle est le seul garde-fou contre un scraping
    en masse du dossier de tous les patients. Taux dans
    `DEFAULT_THROTTLE_RATES["patients"]`.
    """

    scope = "patients"
