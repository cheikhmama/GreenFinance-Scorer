/** Taille de page demandée par les tables de données (plafond serveur des listes Admin). */
export const TAILLE_PAGE_TABLE = 100;

/** Plafond de sécurité : au-delà, la table affiche les 5 000 premières lignes. */
const PAGES_MAX = 50;

/** Charge toutes les pages d'une liste paginée, dans l'ordre (tâche 5.17) : la table de données
 * recherche, filtre, trie et pagine ensuite côté navigateur, ce qui suffit aux volumes de
 * l'Administration. Recherche et tri côté serveur restent possibles plus tard sans toucher aux
 * écrans, en changeant la source de la table. */
export async function chargerToutesLesPages<T>(
  chargerPage: (page: number) => Promise<{ items: T[]; page: number; pages: number }>,
): Promise<T[]> {
  const lignes: T[] = [];
  for (let page = 1; page <= PAGES_MAX; page += 1) {
    const reponse = await chargerPage(page);
    lignes.push(...reponse.items);
    if (reponse.page >= reponse.pages) break;
  }
  return lignes;
}
