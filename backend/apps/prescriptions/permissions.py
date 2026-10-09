"""RBAC prescriptions — divergence délibérée par rapport à
`apps.consultations` : lecture ET écriture ouvertes à médecin ET biologiste
(`IsCliniqueStaffOrSuperAdmin`), pas seulement au médecin. Contrairement à
une consultation (acte strictement médical), le prototype permet au
biologiste d'enregistrer une demande d'examen de façon autonome (écran
"Enregistrer un examen"), sans passage par un médecin — voir models.py.
`super_admin` conserve un accès total, cohérent avec les autres modules."""
from apps.accounts.permissions import role_permission
from apps.accounts.roles import Role

IsCliniqueStaffOrSuperAdmin = role_permission(Role.MEDECIN, Role.BIOLOGISTE, Role.SUPER_ADMIN)
