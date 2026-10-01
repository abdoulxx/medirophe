"""RBAC patients — pas de restriction objet par créateur : un dossier
patient est partagé par toute l'équipe clinique (médecin/biologiste), à la
différence de `User`/`IsSelfOrSuperAdmin` (voir apps/accounts/permissions.py).
`super_admin` est inclus pour rester cohérent avec son accès total déjà
accordé sur `apps.accounts` (support/admin), pas parce que le Ministère
consulte des dossiers patients individuels (hors périmètre MVP §2 : seul un
dashboard agrégé est prévu côté Ministère)."""
from apps.accounts.permissions import role_permission
from apps.accounts.roles import Role

IsCliniqueStaffOrSuperAdmin = role_permission(Role.MEDECIN, Role.BIOLOGISTE, Role.SUPER_ADMIN)
