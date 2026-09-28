import type { EtatPosition } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

const LIBELLES: Record<EtatPosition, string> = {
  PLANIFIEE: "Planifiée",
  ACTIVE: "Active",
  CLOTUREE: "Clôturée",
  ENTREPRISE_SUSPENDUE: "Entreprise suspendue",
};

const VARIANTES: Record<
  EtatPosition,
  "default" | "secondary" | "destructive" | "outline" | "success" | "warning"
> = {
  PLANIFIEE: "secondary",
  ACTIVE: "success",
  CLOTUREE: "outline",
  ENTREPRISE_SUSPENDUE: "destructive",
};

export function libelleEtatPosition(etat: EtatPosition): string {
  return LIBELLES[etat];
}

export function variantEtatPosition(etat: EtatPosition) {
  return VARIANTES[etat];
}

/** Formatte un pourcentage 0-100 (score, couverture) avec une décimale, jamais plus — cohérence
 * d'affichage entre les espaces Investisseur/Chercheur/Institution. */
export function formatScore(valeur: number | null): string {
  return valeur === null ? "—" : `${valeur.toFixed(1)}/100`;
}

/** Seuils d'appréciation d'un score ESG (0-100) pour un badge visuellement remarquable —
 * mêmes seuils que ceux déjà utilisés à l'écran pour la couverture ESG, réutilisés ici pour un
 * score individuel. Un score absent (entreprise sans score calculé) reste neutre. */
export function variantScore(valeur: number | null): "secondary" | "success" | "warning" | "destructive" {
  if (valeur === null) return "secondary";
  if (valeur >= 70) return "success";
  if (valeur >= 40) return "warning";
  return "destructive";
}

export function formatPourcentage(valeur: number): string {
  return `${valeur.toFixed(0)} %`;
}

export function formatMontant(valeur: number, devise: string): string {
  return `${valeur.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} ${devise}`;
}
