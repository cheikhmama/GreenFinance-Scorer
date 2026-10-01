import type { ReportStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

type Variante = "default" | "secondary" | "destructive" | "outline" | "success" | "warning";

/**
 * Libellé et couleur d'un statut de rapport. Depuis la tâche 5.1, un seul statut porte tout le
 * cycle de vie, extraction comprise.
 *
 * Deux lectures du même statut :
 * - rôles internes (Administrateur, Auditeur) : l'état détaillé ;
 * - espace Entreprise : les quatre états d'examen (extraction, attente d'affectation, audit,
 *   décision) sont regroupés en « En cours d'examen » — l'entreprise sait que son rapport est
 *   examiné, pas à quelle étape interne il se trouve. Depuis la tâche 5.9, un brouillon dont le
 *   fichier est en cours de lecture porte le même libellé : aucun état intermédiaire n'est nommé.
 */
const LIBELLES: Record<ReportStatus, string> = {
  DRAFT: "Brouillon",
  EXTRACTING: "Extraction en cours",
  EXTRACTION_FAILED: "Échec de l'extraction",
  AWAITING_ASSIGNMENT: "À affecter",
  IN_AUDIT: "En audit",
  PENDING_DECISION: "En attente de décision",
  REVISION_REQUESTED: "Correction demandée",
  VALIDATED: "Validé",
  REJECTED: "Rejeté",
};

const VARIANTES: Record<ReportStatus, Variante> = {
  DRAFT: "outline",
  EXTRACTING: "secondary",
  EXTRACTION_FAILED: "destructive",
  AWAITING_ASSIGNMENT: "secondary",
  IN_AUDIT: "default",
  PENDING_DECISION: "default",
  REVISION_REQUESTED: "warning",
  VALIDATED: "success",
  REJECTED: "destructive",
};

/** États internes regroupés côté Entreprise. */
export const STATUTS_EN_EXAMEN: readonly ReportStatus[] = [
  "EXTRACTING",
  "AWAITING_ASSIGNMENT",
  "IN_AUDIT",
  "PENDING_DECISION",
];

export const LIBELLE_EN_EXAMEN = "En cours d'examen";

export function libelleStatutRapport(statut: ReportStatus): string {
  return LIBELLES[statut];
}

export function variantStatutRapport(statut: ReportStatus): Variante {
  return VARIANTES[statut];
}

export function estEnExamen(statut: ReportStatus): boolean {
  return STATUTS_EN_EXAMEN.includes(statut);
}

/** Libellé affiché à l'Entreprise (espace Entreprise uniquement). */
export function libelleStatutRapportEntreprise(statut: ReportStatus): string {
  return estEnExamen(statut) ? LIBELLE_EN_EXAMEN : LIBELLES[statut];
}

export function variantStatutRapportEntreprise(statut: ReportStatus): Variante {
  if (statut === "DRAFT") return "secondary";
  if (statut === "VALIDATED") return "outline";
  return estEnExamen(statut) ? "secondary" : VARIANTES[statut];
}

/** Teinte ajoutée au badge Entreprise (tâche 5.9) : « Validé » en contour vert. */
export function classeStatutRapportEntreprise(statut: ReportStatus): string | undefined {
  return statut === "VALIDATED"
    ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-400"
    : undefined;
}

/** Date affichée pour un rapport : son dépôt, ou — pour un brouillon (DRAFT, tâche 1.5), qui n'a
 * encore ni fichier ni date de dépôt — son ouverture. Même règle partout, jamais `new Date(null)`
 * (qui afficherait le 1er janvier 1970). */
export function libelleDateRapport(rapport: { submitted_at: string | null; created_at: string }) {
  return rapport.submitted_at
    ? `Soumis le ${new Date(rapport.submitted_at).toLocaleDateString("fr-FR")}`
    : `Brouillon ouvert le ${new Date(rapport.created_at).toLocaleDateString("fr-FR")}`;
}
