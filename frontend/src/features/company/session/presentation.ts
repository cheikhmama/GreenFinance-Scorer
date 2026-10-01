import type { ReportStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleStatutRapportEntreprise } from "@/shared/format/statut";

/** Présentation d'une session sur la carte « Session active » du tableau de bord Entreprise :
 * un libellé, une couleur et une phrase par état, jamais le nom d'une étape interne. */
export interface PresentationSession {
  libelle: string;
  /** Classes du badge (couleur). */
  ton: string;
  description: string;
}

const EN_EXAMEN: PresentationSession = {
  libelle: "En cours d'examen 🔒",
  ton: "border-transparent bg-brand-blue text-white",
  description: "Votre rapport a été transmis et est en cours d'examen par l'équipe d'audit.",
};

const PRESENTATIONS: Partial<Record<ReportStatus, PresentationSession>> = {
  EXTRACTING: EN_EXAMEN,
  AWAITING_ASSIGNMENT: EN_EXAMEN,
  IN_AUDIT: EN_EXAMEN,
  PENDING_DECISION: EN_EXAMEN,
  DRAFT: {
    libelle: "Brouillon",
    ton: "border-transparent bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
    description:
      "Brouillon en cours de préparation. Remplissez la déclaration et soumettez-la pour examen.",
  },
  REVISION_REQUESTED: {
    libelle: "Précisions requises ⚠️",
    ton: "border-transparent bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300",
    description: "L'auditeur a demandé des précisions ou corrections sur votre rapport.",
  },
  VALIDATED: {
    libelle: "Validé et publié ✓",
    ton: "border-transparent bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300",
    description: "Votre rapport a été validé et votre score officiel est disponible.",
  },
};

/** États hors de la table (échec d'extraction d'un dépôt direct, rejet) : libellé Entreprise
 * habituel, sans phrase dédiée. */
export function presentationSession(statut: ReportStatus): PresentationSession {
  return (
    PRESENTATIONS[statut] ?? {
      libelle: libelleStatutRapportEntreprise(statut),
      ton: "border-transparent bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
      description: "Consultez votre déclaration pour en connaître le détail.",
    }
  );
}
