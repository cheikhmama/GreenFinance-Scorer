import type { Role } from "@/features/auth/schemas";

/** Un seul espace par rôle (voir Utilisateur.role, table à discriminant unique —
 * app/auth/models.py côté backend) : la correspondance est donc directe, sans liste. */
export const ROLE_HOME: Record<Role, string> = {
  ADMIN: "/admin",
  ENTERPRISE: "/company",
  AUDITOR: "/audit",
  INVESTOR: "/investor",
  RESEARCHER: "/researcher",
  INSTITUTION: "/institution",
};

function dansEspace(chemin: string, espace: string): boolean {
  return chemin === espace || chemin.startsWith(`${espace}/`) || chemin.startsWith(`${espace}?`);
}

/** Une page retenue avant la connexion (session expirée) n'est rouverte que si le compte qui se
 * connecte peut la voir : se déconnecter d'un compte Administrateur puis se connecter avec un
 * compte Chercheur renvoyait sur la page Admin quittée, donc sur « Accès non autorisé ». Une page
 * hors de tout espace (profil public, contact…) reste permise. */
export function cheminAutorisePour(role: Role, chemin: string): boolean {
  const espaces = Object.values(ROLE_HOME);
  if (!espaces.some((espace) => dansEspace(chemin, espace))) return true;
  return dansEspace(chemin, ROLE_HOME[role]);
}
