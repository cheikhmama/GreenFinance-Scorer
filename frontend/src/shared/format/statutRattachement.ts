import type { AffiliationStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

const LIBELLES: Record<AffiliationStatus, string> = {
  EN_ATTENTE: "En attente",
  ACCEPTE: "Accepté",
  REFUSE: "Refusé",
};

const VARIANTES: Record<
  AffiliationStatus,
  "default" | "secondary" | "destructive" | "outline" | "success" | "warning"
> = {
  EN_ATTENTE: "warning",
  ACCEPTE: "success",
  REFUSE: "destructive",
};

export function libelleStatutRattachement(statut: AffiliationStatus): string {
  return LIBELLES[statut];
}

export function variantStatutRattachement(statut: AffiliationStatus) {
  return VARIANTES[statut];
}
