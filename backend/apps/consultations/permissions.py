"""RBAC consultations — lecture ouverte à toute l'équipe clinique (médecin +
biologiste), écriture (création/modification) réservée au médecin : c'est
l'acte médical qui produit le dossier, le biologiste n'y écrit jamais (il
reçoit une prescription d'examen distincte, voir la future app dédiée).
`super_admin` conserve un accès total, cohérent avec `apps.patients`."""
from apps.accounts.permissions import role_permission
from apps.accounts.roles import Role

IsCliniqueStaffOrSuperAdmin = role_permission(Role.MEDECIN, Role.BIOLOGISTE, Role.SUPER_ADMIN)
IsMedecinOrSuperAdmin = role_permission(Role.MEDECIN, Role.SUPER_ADMIN)
