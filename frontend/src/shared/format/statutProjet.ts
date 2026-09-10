import type { StatutProjet } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

const LIBELLES: Record<StatutProjet, string> = {
  OUVERT: "Ouvert",
  CLOTURE: "Clôturé",
};

const VARIANTES: Record<
  StatutProjet,
  "default" | "secondary" | "destructive" | "outline" | "success" | "warning"
> = {
  OUVERT: "success",
  CLOTURE: "secondary",
};

export function libelleStatutProjet(statut: StatutProjet): string {
  return LIBELLES[statut];
}

export function variantStatutProjet(statut: StatutProjet) {
  return VARIANTES[statut];
}
