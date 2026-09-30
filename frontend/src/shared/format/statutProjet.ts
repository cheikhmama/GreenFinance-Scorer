import type { ProjectStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

const LIBELLES: Record<ProjectStatus, string> = {
  OUVERT: "Ouvert",
  CLOTURE: "Clôturé",
};

const VARIANTES: Record<
  ProjectStatus,
  "default" | "secondary" | "destructive" | "outline" | "success" | "warning"
> = {
  OUVERT: "success",
  CLOTURE: "secondary",
};

export function libelleStatutProjet(statut: ProjectStatus): string {
  return LIBELLES[statut];
}

export function variantStatutProjet(statut: ProjectStatus) {
  return VARIANTES[statut];
}
