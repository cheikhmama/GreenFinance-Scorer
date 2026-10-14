import type { ReactNode } from "react";
import { cn } from "@/shared/ui/cn";

/** Rail de sections + détail (spec §2.2), à la manière des réglages d'un téléphone : côte à côte
 * à partir de `md` ; en dessous, le rail est masqué dès qu'une section est ouverte (le fil
 * d'Ariane ramène au niveau du rail). */
export function MasterDetailLayout({
  rail,
  railLabel,
  detailActif,
  children,
}: {
  rail: ReactNode;
  /** Nomme le rail quand c'est une navigation ; omis quand le rail porte déjà la sienne
   * (WizardStepper). */
  railLabel?: string;
  detailActif: boolean;
  children: ReactNode;
}) {
  const Rail = railLabel ? "nav" : "div";
  return (
    <div className="grid gap-6 md:grid-cols-[16rem_minmax(0,1fr)]">
      <Rail aria-label={railLabel} className={cn(detailActif && "hidden md:block")}>
        {rail}
      </Rail>
      <div className="min-w-0">{children}</div>
    </div>
  );
}
