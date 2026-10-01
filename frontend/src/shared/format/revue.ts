import type {
  MetricReviewStatus,
  ReviewReason,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

/** Libellés de la revue des valeurs par l'Auditeur (tâches 5.6, 5.7). */
const STATUTS: Record<
  MetricReviewStatus,
  { libelle: string; variante: "outline" | "success" | "warning" | "destructive" }
> = {
  PENDING: { libelle: "À revoir", variante: "outline" },
  ACCEPTED: { libelle: "Acceptée", variante: "success" },
  OVERRIDDEN: { libelle: "Corrigée", variante: "warning" },
  NOT_FOUND: { libelle: "Non trouvée", variante: "destructive" },
};

const MOTIFS: Record<ReviewReason, string> = {
  EXTRACTION_ERROR: "Erreur de lecture",
  UNIT_ERROR: "Erreur d’unité",
  WRONG_PERIOD: "Mauvaise période",
  WRONG_SCOPE: "Mauvais périmètre",
  NOT_IN_SOURCE: "Absente de la source",
  OTHER: "Autre",
};

export const MOTIFS_REVUE = Object.keys(MOTIFS) as ReviewReason[];

export function libelleStatutRevue(statut: MetricReviewStatus): string {
  return STATUTS[statut].libelle;
}

export function variantStatutRevue(statut: MetricReviewStatus) {
  return STATUTS[statut].variante;
}

export function libelleMotifRevue(motif: ReviewReason): string {
  return MOTIFS[motif];
}
