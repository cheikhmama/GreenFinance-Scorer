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

export function formatPourcentage(valeur: number): string {
  return `${valeur.toFixed(0)} %`;
}

export function formatMontant(valeur: number, devise: string): string {
  return `${valeur.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} ${devise}`;
}
