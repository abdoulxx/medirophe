from django.contrib.auth.base_user import BaseUserManager

from .roles import Role


class UserManager(BaseUserManager):
    """Manager custom requis car `User` n'a pas de `username` (login par
    email) et impose un `role` métier obligatoire — Django n'a pas
    d'équivalent générique pour ces deux contraintes.
    """

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("L'adresse email est obligatoire.")
        if not password:
            raise ValueError("Un mot de passe est obligatoire.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Chemin normal (API `/users/` ou scripts) : jamais staff/superuser
        — ces deux flags ne gouvernent que l'accès à /admin/, pas le RBAC
        métier (voir `roles.py`), donc aucune raison de les accorder ici."""
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        if not extra_fields.get("role"):
            raise ValueError("Un rôle métier (role) est obligatoire.")
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """Requis par `manage.py createsuperuser`. Le rôle métier par défaut
        (`super_admin`) est un choix pratique pour le premier compte créé sur
        un environnement neuf, pas une équivalence : `is_superuser` reste
        purement /admin/, `role=super_admin` reste purement RBAC API — les
        deux peuvent diverger ensuite sans problème (ex. retirer is_staff à
        ce compte sans toucher à son rôle métier)."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", Role.SUPER_ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Un superuser doit avoir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Un superuser doit avoir is_superuser=True.")

        return self._create_user(email, password, **extra_fields)
