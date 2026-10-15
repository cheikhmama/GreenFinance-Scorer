import type { ReportStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import type { TonStatut } from "@/shared/ui/status-badge";

/** Les quatre phases d'une déclaration vues par l'Entreprise (spec §5.1). Les étapes internes
 * de l'examen (affectation, audit, décision) restent regroupées (décision 5.1). */
export const PHASES_DECLARATION = [
  "Déposé",
  "Analyse en cours",
  "En cours d’examen",
  "Audité",
] as const;

export type BrancheDeclaration = "ANALYSE_IMPOSSIBLE" | "CORRECTION_DEMANDEE";

export interface PhaseDeclaration {
  index: 0 | 1 | 2 | 3;
  libelle: string;
  ton: TonStatut;
  branche: BrancheDeclaration | null;
}

const ANALYSE_IMPOSSIBLE: PhaseDeclaration = {
  index: 1,
  libelle: "Analyse impossible",
  ton: "danger",
  branche: "ANALYSE_IMPOSSIBLE",
};

const EN_EXAMEN: PhaseDeclaration = {
  index: 2,
  libelle: "En cours d’examen",
  ton: "attention",
  branche: null,
};

export function phaseDeclaration(rapport: {
  status: ReportStatus;
  extraction_error: string | null;
}): PhaseDeclaration {
  switch (rapport.status) {
    case "DRAFT":
      return rapport.extraction_error !== null
        ? ANALYSE_IMPOSSIBLE
        : { index: 0, libelle: "Déposé", ton: "neutre", branche: null };
    case "EXTRACTING":
      return { index: 1, libelle: "Analyse en cours", ton: "info", branche: null };
    case "EXTRACTION_FAILED":
      return ANALYSE_IMPOSSIBLE;
    case "AWAITING_ASSIGNMENT":
    case "IN_AUDIT":
    case "PENDING_DECISION":
      return EN_EXAMEN;
    case "REVISION_REQUESTED":
      return { ...EN_EXAMEN, libelle: "Correction demandée", branche: "CORRECTION_DEMANDEE" };
    case "VALIDATED":
      return { index: 3, libelle: "Validé & publié", ton: "succes", branche: null };
    case "REJECTED":
      return { index: 3, libelle: "Refusé", ton: "danger", branche: null };
  }
}
