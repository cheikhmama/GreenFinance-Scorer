import type { StatutAnalyse } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

const LIBELLES: Record<StatutAnalyse, string> = {
  BROUILLON: "Brouillon",
  SOUMISE: "Soumise",
  VALIDEE: "Validée",
  CORRECTION_DEMANDEE: "Correction demandée",
};

const VARIANTES: Record<
  StatutAnalyse,
  "default" | "secondary" | "destructive" | "outline" | "success" | "warning"
> = {
  BROUILLON: "secondary",
  SOUMISE: "default",
  VALIDEE: "success",
  CORRECTION_DEMANDEE: "warning",
};

export function libelleStatutAnalyse(statut: StatutAnalyse): string {
  return LIBELLES[statut];
}

export function variantStatutAnalyse(statut: StatutAnalyse) {
  return VARIANTES[statut];
}
