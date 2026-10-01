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

export const ETAPES = ["Préparation", "Soumission", "Examen 🔒", "Décision"] as const;

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
