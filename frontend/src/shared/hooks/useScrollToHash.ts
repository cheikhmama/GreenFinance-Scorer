import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/** Fait défiler la page jusqu'à l'élément dont l'id correspond au hash de l'URL (ex.
 * /admin/rapports#en-validation) — React Router ne fait jamais ce défilement automatiquement,
 * contrairement à une ancre HTML classique sur un site non SPA. Utilisé par le tableau de bord
 * Admin pour amener directement sur la section concernée plutôt que sur le haut de la page. */
export function useScrollToHash(deps: readonly unknown[] = []) {
  const { hash } = useLocation();

  useEffect(() => {
    if (!hash) return;
    const cible = document.getElementById(hash.slice(1));
    cible?.scrollIntoView({ behavior: "smooth", block: "start" });
    // deps : fourni par l'appelant pour re-tenter le défilement une fois les données chargées
    // (l'élément ciblé n'existe pas encore tant qu'une section conditionnelle — ex. repliée si
    // vide — n'a pas fini son premier rendu avec des données).
  }, [hash, ...deps]);
}
