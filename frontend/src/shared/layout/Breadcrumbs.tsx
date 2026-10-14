import { ChevronLeft, ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useMatches } from "react-router-dom";
import type { HandleRoute } from "./handle";

interface Etape {
  chemin: string;
  contenu: ReactNode;
}

/** Fil d'Ariane (spec §2.2) : une étape par route qui déclare `handle.fil`. Masqué sur une page
 * de premier niveau ; au téléphone, réduit à un lien vers le niveau parent. */
export function Breadcrumbs() {
  const etapes: Etape[] = useMatches().flatMap((match) => {
    const fil = (match.handle as HandleRoute | undefined)?.fil;
    if (fil === undefined) return [];
    return [{ chemin: match.pathname, contenu: typeof fil === "string" ? fil : fil(match.params) }];
  });
  if (etapes.length < 2) return null;
  const parent = etapes[etapes.length - 2];

  return (
    <nav aria-label="Fil d’Ariane" className="mb-4">
      <Link
        to={parent.chemin}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground sm:hidden"
      >
        <ChevronLeft className="size-4" aria-hidden="true" />
        <span className="sr-only">Retour à</span> {parent.contenu}
      </Link>
      <ol className="hidden flex-wrap items-center gap-1 text-sm text-muted-foreground sm:flex">
        {etapes.map((etape, i) => (
          <li key={etape.chemin} className="flex items-center gap-1">
            {i > 0 ? <ChevronRight className="size-3.5" aria-hidden="true" /> : null}
            {i === etapes.length - 1 ? (
              <span aria-current="page" className="font-medium text-foreground">
                {etape.contenu}
              </span>
            ) : (
              <Link to={etape.chemin} className="hover:text-foreground hover:underline">
                {etape.contenu}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
