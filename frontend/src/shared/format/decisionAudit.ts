import type { AuditDecision } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

/**
 * Libellé d'une recommandation d'audit — partagé par les espaces Auditeur et Administrateur (voir
 * FRONTEND-ARCHITECTURE.md §2.2 : remonté dans shared/ dès qu'un élément a au moins deux usages
 * réels distincts, ici deux, dans deux features différentes).
 */
const LIBELLES: Record<AuditDecision, string> = {
  FAVORABLE: "Favorable",
  FAVORABLE_WITH_RESERVATIONS: "Favorable avec réserves",
  CORRECTION_REQUIRED: "Correction requise",
  UNFAVORABLE: "Défavorable",
};

/** Les quatre avis, dans l'ordre du formulaire (tâche 5.6). */
export const DECISIONS_AUDIT = Object.keys(LIBELLES) as AuditDecision[];

export function libelleDecisionAudit(decision: AuditDecision): string {
  return LIBELLES[decision];
}
