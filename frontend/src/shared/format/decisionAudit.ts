import type { AuditDecision } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

/**
 * Libellé d'une recommandation d'audit — partagé par les espaces Auditeur et Administrateur (voir
 * FRONTEND-ARCHITECTURE.md §2.2 : remonté dans shared/ dès qu'un élément a au moins deux usages
 * réels distincts, ici deux, dans deux features différentes).
 */
const LIBELLES: Record<AuditDecision, string> = {
  RECOMMANDE_VALIDATION: "Validation recommandée",
  RECOMMANDE_REJET: "Rejet recommandé",
  DEMANDE_CLARIFICATION: "Clarification demandée",
};

export function libelleDecisionAudit(decision: AuditDecision): string {
  return LIBELLES[decision];
}
