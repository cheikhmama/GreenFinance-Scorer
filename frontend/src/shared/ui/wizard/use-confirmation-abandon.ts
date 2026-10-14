import { useEffect } from "react";
import { type Location, useBlocker } from "react-router-dom";
import { useConfirm } from "@/shared/ui/confirm-dialog";

/** Avant de quitter un assistant dont la saisie n'existe encore que dans le navigateur (spec
 * §3.1) : confirmation explicite. `doitConfirmer` est évalué au moment de la navigation — lire
 * l'état depuis une ref pour qu'une navigation voulue (après création du brouillon) passe. */
export function useConfirmationAbandon(doitConfirmer: (prochaine: Location) => boolean) {
  const confirm = useConfirm();
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      currentLocation.pathname !== nextLocation.pathname && doitConfirmer(nextLocation),
  );

  useEffect(() => {
    if (blocker.state !== "blocked") return;
    confirm({
      title: "Abandonner la saisie ?",
      description: "Les informations saisies dans cet assistant seront perdues.",
      confirmLabel: "Abandonner",
      cancelLabel: "Continuer la saisie",
      destructive: true,
    }).then((abandonner) => (abandonner ? blocker.proceed() : blocker.reset()));
  }, [blocker, confirm]);
}
