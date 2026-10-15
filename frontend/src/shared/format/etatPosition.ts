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
/** « 66,7 » : virgule décimale française, une décimale (« 70,0 » reste « 70,0 »). */
export function uneDecimale(valeur: number): string {
  return valeur.toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

export function formatScore(valeur: number | null): string {
  return valeur === null ? "—" : `${uneDecimale(valeur)}/100`;
}

/** Seuils d'appréciation d'un score ESG (0-100) — mêmes seuils que ceux déjà utilisés à l'écran
 * pour la couverture ESG, réutilisés ici pour un score individuel. Un score absent (entreprise
 * sans score calculé) n'a pas d'appréciation. */
export function appreciationScore(valeur: number | null): "élevé" | "moyen" | "faible" | null {
  if (valeur === null) return null;
  if (valeur >= 70) return "élevé";
  if (valeur >= 40) return "moyen";
  return "faible";
}

/** Couleur du badge de score. Toujours accompagnée du texte d'appreciationScore : la couleur
 * seule ne doit jamais porter l'appréciation (WCAG 1.4.1). */
export function variantScore(
  valeur: number | null,
): "secondary" | "success" | "warning" | "destructive" {
  const appreciation = appreciationScore(valeur);
  if (appreciation === "élevé") return "success";
  if (appreciation === "moyen") return "warning";
  if (appreciation === "faible") return "destructive";
  return "secondary";
}

/** « 66,7/100 · moyen » — score et appréciation en texte, pour les badges colorés. */
export function formatScoreApprecie(valeur: number | null): string {
  const appreciation = appreciationScore(valeur);
  return appreciation ? `${formatScore(valeur)} · ${appreciation}` : formatScore(valeur);
}

export function formatPourcentage(valeur: number): string {
  return `${valeur.toFixed(0)} %`;
}

export function formatMontant(valeur: number, devise: string): string {
  return `${valeur.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} ${devise}`;
}
