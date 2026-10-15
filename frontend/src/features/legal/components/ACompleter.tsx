import type { ReactNode } from "react";

/** Information légale que seul l'exploitant peut fournir (identité, adresse, contacts, durées de
 * conservation) : visible et surlignée tant qu'elle n'est pas remplie, pour ne jamais publier une
 * mention inventée. Rechercher « ACompleter » pour toutes les retrouver avant la mise en ligne. */
export function ACompleter({ children }: { children: ReactNode }) {
  return (
    <mark className="rounded bg-amber-100 px-1 text-amber-950">[À COMPLÉTER : {children}]</mark>
  );
}
