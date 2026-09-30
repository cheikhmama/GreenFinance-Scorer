import type { AnalysisStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

const LIBELLES: Record<AnalysisStatus, string> = {
  BROUILLON: "Brouillon",
  SOUMISE: "Soumise",
  VALIDEE: "Validée",
  CORRECTION_DEMANDEE: "Correction demandée",
};

const VARIANTES: Record<
  AnalysisStatus,
  "default" | "secondary" | "destructive" | "outline" | "success" | "warning"
> = {
  BROUILLON: "secondary",
  SOUMISE: "default",
  VALIDEE: "success",
  CORRECTION_DEMANDEE: "warning",
};

export function libelleStatutAnalyse(statut: AnalysisStatus): string {
  return LIBELLES[statut];
}

export function variantStatutAnalyse(statut: AnalysisStatus) {
  return VARIANTES[statut];
}
