import { useRef } from "react";

/** Rend le focus, à la fermeture d'un Dialog ou d'un Sheet, à l'élément qui l'avait à l'ouverture
 * (WCAG 2.4.3). Radix ne le rend qu'à un Trigger : la plupart des fenêtres de l'application sont
 * contrôlées (`open` piloté par l'état) sans Trigger, et le focus retombait sur <body>.
 *
 * onOpenAutoFocus est émis par le FocusScope de Radix avant qu'il ne déplace le focus : l'élément
 * actif est encore celui qui a ouvert la fenêtre. Les gestionnaires passés par l'appelant
 * s'exécutent d'abord ; s'il annule l'événement, son propre choix de focus est respecté. Un
 * ouvreur retiré entre-temps de la page (menu refermé, ligne supprimée) laisse le comportement
 * de Radix s'appliquer. */
export function useRetourFocus(
  onOpenAutoFocus?: (event: Event) => void,
  onCloseAutoFocus?: (event: Event) => void,
) {
  const ouvreur = useRef<HTMLElement | null>(null);
  return {
    onOpenAutoFocus(event: Event) {
      const actif = document.activeElement;
      ouvreur.current = actif instanceof HTMLElement && actif !== document.body ? actif : null;
      onOpenAutoFocus?.(event);
    },
    onCloseAutoFocus(event: Event) {
      onCloseAutoFocus?.(event);
      const element = ouvreur.current;
      ouvreur.current = null;
      if (event.defaultPrevented || !element?.isConnected) return;
      event.preventDefault();
      element.focus();
    },
  };
}
