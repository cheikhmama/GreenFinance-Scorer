import { useSearchParams } from "react-router-dom";

/** Lit/écrit un unique paramètre de recherche dans l'URL, avec une valeur par défaut — même usage
 * qu'un useState, mais partageable par lien (ex. une carte du tableau de bord déposant directement
 * sur le bon filtre) et survit à un rafraîchissement de page. Ne valide pas contre un ensemble
 * autorisé — convient à un filtre simple (statut, recherche) où une valeur invalide ne fait que
 * renvoyer une liste vide, jamais casser l'affichage (contrairement à un onglet actif, voir
 * AdminReportsPage/AdminCompaniesPage pour ce cas, qui valident explicitement). */
export function useOngletParametre<T extends string>(
  cle: string,
  valeurParDefaut: T,
): [T, (valeur: T) => void] {
  const [searchParams, setSearchParams] = useSearchParams();
  const valeur = (searchParams.get(cle) as T | null) ?? valeurParDefaut;

  function definir(nouvelleValeur: T) {
    setSearchParams(
      (params) => {
        if (nouvelleValeur) {
          params.set(cle, nouvelleValeur);
        } else {
          params.delete(cle);
        }
        return params;
      },
      { replace: true },
    );
  }

  return [valeur, definir];
}
