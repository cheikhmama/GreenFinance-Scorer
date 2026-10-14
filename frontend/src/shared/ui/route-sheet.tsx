import { type ReactNode, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "./sheet";

/** Tiroir adressable (refonte de la navigation, spec §7.1) : ouvert tant que sa route est active,
 * le fermer (Échap, ×, clic à côté) ramène à `retour`, la route parente. Le focus revient à
 * l'élément qui l'a ouvert (Radix le mémorise au montage et le rend au démontage). */
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
  // Radix rend le focus au Trigger ; un tiroir routé n'en a pas, on rend donc le focus à l'élément
  // qui était actif à l'ouverture (absent sur un lien profond : rien à faire).
  const [ouvreur] = useState(() =>
    document.activeElement instanceof HTMLElement ? document.activeElement : null,
  );
  return (
    <Sheet
      open
      onOpenChange={(ouvert) => {
        if (!ouvert) navigate(retour, { preventScrollReset: true });
      }}
    >
      <SheetContent
        taille={taille}
        onCloseAutoFocus={(event) => {
          if (ouvreur?.isConnected) {
            event.preventDefault();
            ouvreur.focus();
          }
        }}
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
