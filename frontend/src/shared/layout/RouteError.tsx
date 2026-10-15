import { FileWarning } from "lucide-react";
import { Link, useRouteError } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";

/** Erreur imprévue d'un niveau de navigation (spec §6) : message utile, reprise, identifiant de
 * corrélation copiable — jamais de pile ni de charge brute. */
export function RouteError() {
  const erreur = useRouteError();
  const correlation = erreur instanceof ApiError ? erreur.correlationId : null;
  return (
    <Card role="alert">
      <CardContent className="flex flex-col items-center gap-3 py-6 text-center">
        <FileWarning className="size-8 text-muted-foreground" aria-hidden="true" />
        <p className="font-medium text-foreground">Cette section n’a pas pu s’afficher.</p>
        {correlation ? (
          <p className="text-xs text-muted-foreground">
            Référence : <code className="select-all font-mono">{correlation}</code>
          </p>
        ) : null}
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => window.location.reload()}>
            Réessayer
          </Button>
          <Button asChild variant="ghost">
            <Link to="..">Niveau précédent</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
