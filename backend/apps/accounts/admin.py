"""Admin Django (`/admin/`) — distinct de l'API : sert au support/ops, pas au
RBAC métier. Un accès /admin/ est gouverné par `is_staff`/`is_superuser`, pas
par `role` (voir `models.py`)."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Étend l'UserAdmin Django standard (gestion password hashée, etc.) en
    remplaçant `username` par `email`/`role` dans les fieldsets, puisque
    `User` n'a pas de champ `username`."""

    ordering = ["email"]
    list_display = ["email", "role", "is_active", "is_staff", "date_joined"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informations personnelles", {"fields": ("first_name", "last_name")}),
        ("Rôle & accès", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "role", "password1", "password2"),
            },
        ),
    )
    readonly_fields = ["date_joined"]
