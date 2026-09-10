import type { StatutRapport } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

/**
 * Libellé et couleur d'un statut de rapport — partagé par les espaces Entreprise, Administrateur
 * et Auditeur (voir FRONTEND-ARCHITECTURE.md §2.2 : remonté dans shared/ dès qu'un élément a au
 * moins deux usages réels distincts, ici trois).
 */
const LIBELLES: Record<StatutRapport, string> = {
  ENVOYE: "Envoyé",
  EN_EXTRACTION: "Extraction en cours",
  AFFECTE_AUDITEUR: "Affecté à un auditeur",
  EN_VALIDATION: "En attente de décision",
  VALIDE: "Validé",
  REJETE: "Rejeté",
  DEMANDE_CORRECTION: "Correction demandée",
};

const VARIANTES: Record<
  StatutRapport,
  "default" | "secondary" | "destructive" | "outline" | "success" | "warning"
> = {
  ENVOYE: "secondary",
  EN_EXTRACTION: "secondary",
  AFFECTE_AUDITEUR: "default",
  EN_VALIDATION: "default",
  VALIDE: "success",
  REJETE: "destructive",
  DEMANDE_CORRECTION: "warning",
};

export function libelleStatutRapport(statut: StatutRapport): string {
  return LIBELLES[statut];
}

export function variantStatutRapport(statut: StatutRapport) {
  return VARIANTES[statut];
}
