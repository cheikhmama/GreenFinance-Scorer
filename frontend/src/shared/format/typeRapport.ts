import type { ReportType } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

/** Libellés lisibles des types de rapport (tâche 5.9) : jamais le code technique à l'écran. */
const LIBELLES: Record<ReportType, string> = {
  RAPPORT_ANNUEL: "Rapport annuel",
  RAPPORT_ESG: "Rapport ESG",
  RAPPORT_CLIMAT: "Rapport climat",
};

export function libelleTypeRapport(type: ReportType): string {
  return LIBELLES[type] ?? type;
}

/** « Rapport ESG — Exercice 2026 », et la version quand c'est une correction. */
export function titreDeclaration(rapport: {
  type: ReportType;
  fiscal_year: number | null;
  version?: number;
}): string {
  const exercice =
    rapport.fiscal_year === null ? "exercice inconnu" : `Exercice ${rapport.fiscal_year}`;
  const version = rapport.version && rapport.version > 1 ? ` (version ${rapport.version})` : "";
  return `${libelleTypeRapport(rapport.type)} — ${exercice}${version}`;
}
