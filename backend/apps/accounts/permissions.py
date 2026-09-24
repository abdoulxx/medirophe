"""
Permissions RBAC.

Pattern à réutiliser par toutes les futures apps (patients, consultations...) :
1. `DEFAULT_PERMISSION_CLASSES = (IsAuthenticated,)` dans settings = refus par
   défaut, jamais d'accès anonyme implicite sur une vue qui oublierait de
   déclarer ses permissions.
2. Une permission de *rôle* (`HasRole`) contrôle qui a le droit d'atteindre
   un type de vue.
3. Une permission *objet* (`has_object_permission`) contrôle si l'utilisateur
   a le droit sur CETTE instance précise (protection IDOR/BOLA) — jamais
   uniquement via un filtre dans la vue : le queryset de `get_queryset` doit
   lui aussi être borné (voir apps/accounts/views.py pour l'exemple).
"""
from rest_framework.permissions import BasePermission

from .roles import Role


class HasRole(BasePermission):
    """Permission de base : accès réservé aux rôles listés dans `allowed_roles`.
    Un utilisateur non authentifié, ou dont le rôle n'est pas listé, est
    toujours refusé — il n'y a pas de rôle "par défaut" autorisé.
    """

    allowed_roles: frozenset = frozenset()

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.allowed_roles)


def role_permission(*roles):
    """Fabrique une permission DRF restreinte aux rôles donnés."""
    return type("RolePermission", (HasRole,), {"allowed_roles": frozenset(roles)})


IsMedecin = role_permission(Role.MEDECIN)
IsBiologiste = role_permission(Role.BIOLOGISTE)
IsCliniqueStaff = role_permission(Role.MEDECIN, Role.BIOLOGISTE)
IsSuperAdmin = role_permission(Role.SUPER_ADMIN)
IsAdmin = role_permission(Role.SUPER_ADMIN, Role.ADMIN)
IsMinistereStaff = role_permission(Role.SUPER_ADMIN, Role.ADMIN, Role.ANALYSTE)


class IsSelfOrSuperAdmin(BasePermission):
    """Permission objet : un utilisateur ne peut consulter que sa propre
    fiche, sauf un super administrateur qui peut consulter n'importe
    quelle fiche (nécessaire pour l'écran Ministère "Utilisateurs & droits
    d'accès"). C'est l'exemple concret d'IDOR à reproduire pour les futures
    ressources patient : "self OR rôle habilité", jamais "tout le monde".
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        return obj.pk == user.pk or user.role == Role.SUPER_ADMIN
