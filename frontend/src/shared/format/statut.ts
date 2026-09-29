import type {
  ExtractionStatus,
  ReportStatus,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

/**
 * Libellé et couleur d'un statut de rapport — partagé par les espaces Entreprise, Administrateur
 * et Auditeur (voir FRONTEND-ARCHITECTURE.md §2.2 : remonté dans shared/ dès qu'un élément a au
 * moins deux usages réels distincts, ici trois).
 *
 * Depuis le découpage statut métier / avancement de l'extraction (docs/RENAME_PLAN.md §2.4), un
 * rapport SUBMITTED reste SUBMITTED pendant toute son extraction : quand l'appelant connaît
 * `statut_extraction`, il le transmet pour distinguer « Envoyé » (en file) de « Extraction en
 * cours » (démarrée, terminée en attente d'affectation, ou en échec) — mêmes libellés qu'avant le
 * découpage. Sans lui (ex. dernier statut d'une entreprise), le libellé générique « Soumis ».
 */
const LIBELLES: Record<ReportStatus, string> = {
  DRAFT: "Brouillon",
  SUBMITTED: "Soumis",
  PENDING_AUDIT: "Affecté à un auditeur",
  PENDING_DECISION: "En attente de décision",
  VALIDATED: "Validé",
  REJECTED: "Rejeté",
  REVISION_REQUESTED: "Correction demandée",
};

const VARIANTES: Record<
  ReportStatus,
  "default" | "secondary" | "destructive" | "outline" | "success" | "warning"
> = {
  DRAFT: "outline",
  SUBMITTED: "secondary",
  PENDING_AUDIT: "default",
  PENDING_DECISION: "default",
  VALIDATED: "success",
  REJECTED: "destructive",
  REVISION_REQUESTED: "warning",
};

export function libelleStatutRapport(
  statut: ReportStatus,
  statutExtraction?: ExtractionStatus,
): string {
  if (statut === "SUBMITTED" && statutExtraction !== undefined) {
    return statutExtraction === "QUEUED" || statutExtraction === "NOT_STARTED"
      ? "Envoyé"
      : "Extraction en cours";
  }
  return LIBELLES[statut];
}

export function variantStatutRapport(statut: ReportStatus) {
  return VARIANTES[statut];
}
