/** Taille de page demandée par les tables de données (plafond serveur des listes Admin). */
export const TAILLE_PAGE_TABLE = 100;

/** Plafond de sécurité : au-delà, la table n'a que les LIGNES_MAX premières lignes. */
const PAGES_MAX = 50;
export const LIGNES_MAX = PAGES_MAX * TAILLE_PAGE_TABLE;

/** Pages demandées en même temps après la première. */
const REQUETES_SIMULTANEES = 4;

type ChargerPage<T> = (page: number) => Promise<{ items: T[]; page: number; pages: number }>;

export interface ToutesLesPages<T> {
  lignes: T[];
  /** Vrai : la liste dépasse LIGNES_MAX, seules les premières lignes sont chargées. */
  tronque: boolean;
}

/** Charge toutes les pages d'une liste paginée (tâche 5.17) : la première donne le nombre de
 * pages, les suivantes partent ensuite REQUETES_SIMULTANEES à la fois, l'ordre étant conservé. La
 * table de données recherche, filtre, trie et pagine ensuite côté navigateur, ce qui suffit aux
 * volumes de l'Administration. Recherche et tri côté serveur restent possibles plus tard sans
 * toucher aux écrans, en changeant la source de la table. */
export async function chargerToutesLesPagesAvecEtat<T>(
  chargerPage: ChargerPage<T>,
): Promise<ToutesLesPages<T>> {
  const premiere = await chargerPage(1);
  const derniere = Math.min(premiere.pages, PAGES_MAX);
  const suivantes: T[][] = [];
  let prochaine = 2;
  async function charger() {
    while (prochaine <= derniere) {
      const page = prochaine;
      prochaine += 1;
      suivantes[page - 2] = (await chargerPage(page)).items;
    }
  }
  await Promise.all(
    Array.from({ length: Math.min(REQUETES_SIMULTANEES, Math.max(0, derniere - 1)) }, charger),
  );
  return { lignes: [...premiere.items, ...suivantes.flat()], tronque: premiere.pages > PAGES_MAX };
}

/** chargerToutesLesPagesAvecEtat pour les listes qui ne signalent pas la troncature. */
export async function chargerToutesLesPages<T>(chargerPage: ChargerPage<T>): Promise<T[]> {
  return (await chargerToutesLesPagesAvecEtat(chargerPage)).lignes;
}
