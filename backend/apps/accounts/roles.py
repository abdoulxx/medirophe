from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    """Rôles métier multi-portails (distinct de is_staff/is_superuser, qui
    ne gouvernent que l'accès à /admin/, pas les permissions API).

    Portail Clinique & Labo : BIOLOGISTE, MEDECIN.
    Portail Ministère de la Santé : SUPER_ADMIN, ADMIN, ANALYSTE.
    """

    BIOLOGISTE = "biologiste", _("Biologiste")
    MEDECIN = "medecin", _("Médecin")
    SUPER_ADMIN = "super_admin", _("Super administrateur")
    ADMIN = "admin", _("Administrateur")
    ANALYSTE = "analyste", _("Analyste")


CLINIQUE_ROLES = frozenset({Role.BIOLOGISTE, Role.MEDECIN})
MINISTERE_ROLES = frozenset({Role.SUPER_ADMIN, Role.ADMIN, Role.ANALYSTE})
