import type { ReportStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleStatutRapportEntreprise } from "@/shared/format/statut";

/** Présentation d'une session sur le tableau de bord Entreprise : un libellé sobre, une teinte
 * pastel avec sa pastille, une phrase par état — jamais le nom d'une étape interne. */
export interface PresentationSession {
  libelle: string;
  /** Classes de la pastille d'état (fond clair, texte foncé, bordure fine). */
  ton: string;
  /** Classe de couleur de la pastille ronde devant le libellé. */
  point: string;
  description: string;
}

const NEUTRE = {
  ton: "border-slate-200 bg-slate-100 text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200",
  point: "bg-slate-400",
};

const EN_EXAMEN: PresentationSession = {
  libelle: "En cours d'examen",
  ton: "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900 dark:bg-blue-950/60 dark:text-blue-300",
  point: "bg-blue-500",
  description: "Votre rapport a été transmis et est en cours d'examen par l'équipe d'audit.",
};

const PRESENTATIONS: Partial<Record<ReportStatus, PresentationSession>> = {
  EXTRACTING: EN_EXAMEN,
  AWAITING_ASSIGNMENT: EN_EXAMEN,
  IN_AUDIT: EN_EXAMEN,
  PENDING_DECISION: EN_EXAMEN,
  DRAFT: {
    libelle: "Brouillon",
    ...NEUTRE,
    description:
      "Brouillon en cours de préparation. Remplissez la déclaration et soumettez-la pour examen.",
  },
  REVISION_REQUESTED: {
    libelle: "Correction demandée",
    ton: "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-300",
    point: "bg-amber-500",
    description: "L'auditeur a demandé des précisions ou corrections sur votre rapport.",
  },
  VALIDATED: {
    libelle: "Validé & Publié",
    ton: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-300",
    point: "bg-emerald-500",
    description: "Votre rapport a été validé et votre score officiel est disponible.",
  },
};

/** États hors de la table (échec d'extraction d'un dépôt direct, rejet) : libellé Entreprise
 * habituel, teinte neutre. */
export function presentationSession(statut: ReportStatus): PresentationSession {
  return (
    PRESENTATIONS[statut] ?? {
      libelle: libelleStatutRapportEntreprise(statut),
      ...NEUTRE,
      description: "Consultez votre déclaration pour en connaître le détail.",
    }
  );
}

/** Le dernier exercice validé à montrer à côté d'une session active : jamais celui de la session
 * en cours ni un plus récent — sinon la carte du score contredirait la session (« FY2025 en
 * examen » et « score FY2025 » côte à côte). Sans session active, le dernier validé. */
export function dernierScoreAffichable<
  T extends {
    status: ReportStatus;
    fiscal_year: number | null;
    submitted_at: string | null;
    official_global_score?: number | null;
  },
>(rapports: T[], active: { fiscal_year: number | null } | undefined): T | undefined {
  const plafond = active?.fiscal_year ?? null;
  return rapports
    .filter(
      (r) =>
        r.status === "VALIDATED" &&
        r.official_global_score != null &&
        (plafond === null || (r.fiscal_year !== null && r.fiscal_year < plafond)),
    )
    .sort(
      (a, b) =>
        (b.fiscal_year ?? 0) - (a.fiscal_year ?? 0) ||
        (b.submitted_at ?? "").localeCompare(a.submitted_at ?? ""),
    )[0];
}
