import type { ReportStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleStatutRapportEntreprise } from "@/shared/format/statut";

/** État d'une session sur la carte « Session active » du tableau de bord Entreprise : un libellé
 * et une phrase, jamais le nom d'une étape interne. */
export interface PresentationSession {
  libelle: string;
  description: string;
}

const EN_EXAMEN: PresentationSession = {
  libelle: "En cours d'examen",
  description:
    "Votre rapport a été transmis. Vous serez notifié dès la validation finale de l'auditeur.",
};

const PRESENTATIONS: Partial<Record<ReportStatus, PresentationSession>> = {
  EXTRACTING: EN_EXAMEN,
  AWAITING_ASSIGNMENT: EN_EXAMEN,
  IN_AUDIT: EN_EXAMEN,
  PENDING_DECISION: EN_EXAMEN,
  DRAFT: {
    libelle: "Brouillon",
    description:
      "Brouillon en cours de préparation. Remplissez la déclaration et soumettez-la pour examen.",
  },
  REVISION_REQUESTED: {
    libelle: "Correction demandée",
    description: "L'auditeur a demandé des précisions ou corrections sur votre rapport.",
  },
  VALIDATED: {
    libelle: "Validé & Publié",
    description: "Votre rapport a été validé et votre score officiel est disponible.",
  },
};

/** États hors de la table (échec d'extraction d'un dépôt direct, rejet) : libellé Entreprise
 * habituel. */
export function presentationSession(statut: ReportStatus): PresentationSession {
  return (
    PRESENTATIONS[statut] ?? {
      libelle: libelleStatutRapportEntreprise(statut),
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
