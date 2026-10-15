import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "./sheet";

/** Tiroir adressable (refonte de la navigation, spec §7.1) : ouvert tant que sa route est active,
 * le fermer (Échap, ×, clic à côté) ramène à `retour`, la route parente. Le focus revient à
 * l'élément qui l'a ouvert (SheetContent, via useRetourFocus), bien qu'un tiroir routé n'ait pas
 * de Trigger. */
export function RouteSheet({
  retour,
  titre,
  description,
  taille,
  children,
}: {
  retour: string;
  titre: ReactNode;
  description?: ReactNode;
  taille?: "standard" | "large";
  children: ReactNode;
}) {
  const navigate = useNavigate();
  return (
    <Sheet
      open
      onOpenChange={(ouvert) => {
        if (!ouvert) navigate(retour, { preventScrollReset: true });
      }}
    >
      <SheetContent
        taille={taille}
        {...(description ? {} : { "aria-describedby": undefined })}
      >
        <SheetHeader>
          <SheetTitle>{titre}</SheetTitle>
          {description ? <SheetDescription>{description}</SheetDescription> : null}
        </SheetHeader>
        {children}
      </SheetContent>
    </Sheet>
  );
}
