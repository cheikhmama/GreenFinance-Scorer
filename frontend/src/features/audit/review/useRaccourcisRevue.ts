import { useEffect, useRef } from "react";

export interface RaccourcisRevue {
  accepter: () => void;
  corriger: () => void;
  nonTrouvee: () => void;
  suivante: () => void;
  precedente: () => void;
}

/** Vrai quand la frappe vise un champ : un raccourci ne doit jamais voler une saisie. */
function saisieEnCours(cible: EventTarget | null): boolean {
  if (!(cible instanceof HTMLElement)) return false;
  return (
    cible.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(cible.tagName) ||
    cible.closest("[role='dialog']") !== null
  );
}

/** Raccourcis de l'espace de revue (tâche 5.7) : A accepter, E corriger, N non trouvée, J suivante,
 * K précédente. Inactifs pendant une saisie, avec un modificateur (Ctrl, Alt, Meta), dans une
 * fenêtre de dialogue, ou quand `actifs` est faux. */
export function useRaccourcisRevue(raccourcis: RaccourcisRevue, actifs: boolean) {
  const courants = useRef(raccourcis);
  courants.current = raccourcis;

  useEffect(() => {
    if (!actifs) return;
    function surTouche(event: KeyboardEvent) {
      if (event.ctrlKey || event.altKey || event.metaKey || event.repeat) return;
      if (saisieEnCours(event.target)) return;
      const action = {
        a: courants.current.accepter,
        e: courants.current.corriger,
        n: courants.current.nonTrouvee,
        j: courants.current.suivante,
        k: courants.current.precedente,
      }[event.key.toLowerCase()];
      if (!action) return;
      event.preventDefault();
      action();
    }
    window.addEventListener("keydown", surTouche);
    return () => window.removeEventListener("keydown", surTouche);
  }, [actifs]);
}
