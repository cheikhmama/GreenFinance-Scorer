/** Nom d'un pays pour l'affichage. Les entreprises inscrites par le formulaire (tâche 5.10)
 * enregistrent le code ISO (« MR »), celles du jeu de démonstration un nom (« France ») : un code
 * de deux lettres est traduit par la locale française du navigateur, un nom est gardé tel quel. */
const nomsDePays = new Intl.DisplayNames(["fr"], { type: "region" });

export function libellePays(pays: string | null | undefined): string {
  if (!pays) return "—";
  if (!/^[A-Z]{2}$/.test(pays)) return pays;
  try {
    return nomsDePays.of(pays) ?? pays;
  } catch {
    return pays;
  }
}
