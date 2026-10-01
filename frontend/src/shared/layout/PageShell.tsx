import type { ReactNode } from "react";
import { PageHeader } from "@/shared/ui/page-header";

/** Gabarit commun de toutes les pages d'espace : l'en-tête standard (PageHeader) puis le contenu,
 * séparés et espacés de la même façon partout. La largeur maximale (max-w-7xl) et la marge
 * extérieure sont posées une seule fois par AppShell autour de `<Outlet />`, pour que les pages
 * en pleine largeur (`handle: { pleineLargeur: true }`) gardent le même gabarit. */
export function PageShell({
  title,
  description,
  actions,
  children,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="space-y-6">
      <PageHeader title={title} description={description} action={actions} />
      {children}
    </div>
  );
}
