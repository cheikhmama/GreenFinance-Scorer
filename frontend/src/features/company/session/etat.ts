import type {
  GroupeCompletude,
  ReportStatus,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

/** Le minimum d'un rapport pour situer une déclaration dans son cycle (tâche 5.8). */
export interface RapportSession {
  status: ReportStatus;
  submitted_at: string | null;
  source_file: string | null;
  extraction_finished_at: string | null;
  extraction_error: string | null;
}

/** Où en est un brouillon : sans fichier, fichier en analyse, analyse en échec, prêt à soumettre.
 * Null une fois le rapport soumis. */
export type EtatBrouillon = "SANS_FICHIER" | "ANALYSE" | "ECHEC" | "PRET";

export function etatBrouillon(rapport: RapportSession): EtatBrouillon | null {
  if (rapport.submitted_at !== null) return null;
  if (rapport.status === "EXTRACTING") return "ANALYSE";
  if (rapport.extraction_error !== null) return "ECHEC";
  if (rapport.source_file === null || rapport.extraction_finished_at === null)
    return "SANS_FICHIER";
  return "PRET";
}

export const ETAPES = ["Préparation", "Soumission", "Examen", "Décision"] as const;

const DECISIONS: readonly ReportStatus[] = ["VALIDATED", "REJECTED", "REVISION_REQUESTED"];

/** Étape courante du stepper : 0 tant que la déclaration n'est pas soumise, 2 pendant l'examen,
 * 3 une fois la décision rendue (toutes les étapes sont alors franchies). */
export function etapeCourante(rapport: RapportSession): number {
  if (rapport.submitted_at === null) return 0;
  return DECISIONS.includes(rapport.status) ? 3 : 2;
}

const LIBELLES_GROUPES: Record<string, string> = {
  CARBON: "Émissions carbone",
  ENVIRONNEMENT: "Environnement",
  SOCIAL: "Social",
  GOUVERNANCE: "Gouvernance",
};

export function libelleGroupe(groupe: string): string {
  return LIBELLES_GROUPES[groupe] ?? groupe;
}

export function totaux(groupes: GroupeCompletude[]) {
  return groupes.reduce(
    (total, g) => ({ expected: total.expected + g.expected, found: total.found + g.found }),
    { expected: 0, found: 0 },
  );
}

export function dateHeure(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { dateStyle: "long", timeStyle: "short" });
}

/** Le minimum d'un rapport pour le ranger entre « en cours » et « historique » (tâche 5.9). */
interface RapportListe {
  id: string;
  status: ReportStatus;
  fiscal_year: number | null;
  previous_report_id: string | null;
  created_at: string;
}

/** États qui ne retiennent plus l'entreprise — même règle que le serveur
 * (app/company/rapports.py::STATUTS_SANS_SESSION). */
const STATUTS_SANS_SESSION: readonly ReportStatus[] = [
  "VALIDATED",
  "REJECTED",
  "EXTRACTION_FAILED",
];

/** Range les déclarations (tâche 5.9), chaque groupe de la plus récente à la plus ancienne :
 * - `enCours` : au plus une session, la plus récente, jamais d'un exercice déjà validé ;
 * - `historique` : décisions rendues, extractions en échec et versions remplacées par une
 *   correction ;
 * - `sessionBloquante` : la déclaration active qui empêche d'en ouvrir une autre (le serveur
 *   refuse alors l'ouverture : `declaration_en_cours`). */
export function separerDeclarations<T extends RapportListe>(rapports: T[]) {
  const remplaces = new Set(rapports.map((r) => r.previous_report_id).filter(Boolean));
  const tries = [...rapports].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
  const close = (r: T) => STATUTS_SANS_SESSION.includes(r.status) || remplaces.has(r.id);
  const exercicesValides = new Set(
    rapports.filter((r) => r.status === "VALIDATED").map((r) => r.fiscal_year),
  );
  const actifs = tries.filter((r) => !close(r));
  const enCours = actifs.filter((r) => !exercicesValides.has(r.fiscal_year)).slice(0, 1);
  return {
    enCours,
    historique: tries.filter(close),
    // La session montrée d'abord : nommer une déclaration masquée (donnée héritée) dérouterait.
    sessionBloquante: enCours[0] ?? actifs[0],
  };
}

export function libelleExercice(annee: number | null): string {
  return annee === null ? "Exercice inconnu" : `FY${annee}`;
}
