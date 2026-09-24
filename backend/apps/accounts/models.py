"""Modèle utilisateur custom. Voir `roles.py` pour les valeurs de `role` et
`managers.py` pour la création de compte (`create_user`/`create_superuser`)."""
import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _

from .managers import UserManager
from .roles import CLINIQUE_ROLES, MINISTERE_ROLES, Role


class User(AbstractBaseUser, PermissionsMixin):
    """Utilisateur applicatif.

    - Identifiant public en UUID (non séquentiel, non devinable) plutôt
      qu'un entier auto-incrémenté, pour ne pas faciliter l'énumération
      d'identifiants dans les URLs de l'API (protection IDOR/BOLA).
    - `role` porte le RBAC métier ; `is_staff`/`is_superuser` (fournis par
      PermissionsMixin) ne gouvernent que l'accès à /admin/ et restent
      indépendants du rôle métier.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("adresse email"), unique=True, db_index=True)
    first_name = models.CharField(_("prénom"), max_length=150, blank=True)
    last_name = models.CharField(_("nom"), max_length=150, blank=True)
    role = models.CharField(_("rôle"), max_length=32, choices=Role.choices)

    is_active = models.BooleanField(_("actif"), default=True)
    is_staff = models.BooleanField(_("accès admin Django"), default=False)
    date_joined = models.DateTimeField(_("date d'inscription"), auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["role"]

    class Meta:
        verbose_name = _("utilisateur")
        verbose_name_plural = _("utilisateurs")
        ordering = ["email"]

    def __str__(self):
        return f"{self.email} ({self.role})"

    @property
    def is_clinique_role(self):
        """True pour biologiste/médecin (portail Clinique & Labo)."""
        return self.role in CLINIQUE_ROLES

    @property
    def is_ministere_role(self):
        """True pour super_admin/admin/analyste (portail Ministère)."""
        return self.role in MINISTERE_ROLES
