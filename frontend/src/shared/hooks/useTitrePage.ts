import { useEffect } from "react";

export const NOM_APPLICATION = "GreenFinance-Scorer";

/** Titre de l'onglet propre à chaque page (WCAG 2.4.2) : « Titre · GreenFinance-Scorer ». Sans
 * titre, le nom de l'application seul. Appelé par PageHeader (pages connectées) et AuthLayout
 * (pages publiques) : aucune page n'a à le faire elle-même. */
export function useTitrePage(titre: string | null | undefined) {
  useEffect(() => {
    const propre = titre?.trim();
    document.title = propre ? `${propre} · ${NOM_APPLICATION}` : NOM_APPLICATION;
  }, [titre]);
}
