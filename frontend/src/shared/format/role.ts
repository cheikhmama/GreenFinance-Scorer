import type { Role } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

/** Libellé d'un rôle à l'écran — jamais le code (« AUDITOR »). */
const LIBELLES: Record<Role, string> = {
  ADMIN: "Administrateur",
  ENTERPRISE: "Entreprise",
  AUDITOR: "Auditeur",
  INVESTOR: "Investisseur",
  RESEARCHER: "Chercheur",
  INSTITUTION: "Institution",
};

export function libelleRole(role: Role): string {
  return LIBELLES[role] ?? role;
}
