/** Dernier segment d'URL lisible (tâche post-5.17bis) : `{libellé-normalisé}-{uuid}`, jamais
 * l'UUID seul. L'UUID complet est conservé en fin de segment — c'est lui qui fait foi pour
 * retrouver la ressource, le préfixe n'est que cosmétique. Ce choix évite tout changement
 * backend : pas de colonne slug à ajouter, pas de contrainte d'unicité par entité (aucune des
 * entités concernées n'a de nom réellement unique — voir l'exploration qui a précédé ce plan),
 * et un renommage ultérieur ne casse jamais un lien déjà partagé (le préfixe devient juste
 * obsolète visuellement, la résolution reste correcte). Un UUID brut en entrée (ancien lien
 * d'e-mail, notification qui ne connaît que l'id) est un slug valide à préfixe vide : aucune
 * route héritée n'a besoin d'un traitement spécial. */

const RE_UUID_FINAL =
  /([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i;

// Plage Unicode des diacritiques combinants (U+0300-U+036F) laissés par normalize("NFKD") —
// écrite en \u explicite plutôt qu'en caractères littéraux, pour rester lisible et non ambiguë
// dans n'importe quel éditeur/encodage.
const RE_DIACRITIQUES = /[̀-ͯ]/g;

const LONGUEUR_MAX_PREFIXE = 60;

function normaliser(libelle: string): string {
  const net = libelle
    .normalize("NFKD")
    .replace(RE_DIACRITIQUES, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return net.slice(0, LONGUEUR_MAX_PREFIXE).replace(/-+$/g, "");
}

/** `libelle` vide/absent (ex. notification qui ne connaît que l'id) → l'UUID seul, toujours un
 * segment valide. */
export function creerSlug(libelle: string | null | undefined, id: string): string {
  const prefixe = libelle ? normaliser(libelle) : "";
  return prefixe ? `${prefixe}-${id}` : id;
}

/** Robuste à un slug neuf (`mon-portefeuille-<uuid>`) comme à un UUID brut hérité (`<uuid>`) —
 * seul le motif d'UUID en fin de chaîne est significatif, le préfixe n'est jamais interprété. */
export function idDepuisSlug(segment: string): string {
  const trouve = RE_UUID_FINAL.exec(segment);
  return trouve ? trouve[1] : segment;
}
