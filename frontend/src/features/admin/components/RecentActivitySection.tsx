import { History } from "lucide-react";
import { Link } from "react-router-dom";
import { libelleActionJournal, libelleTypeRessource } from "@/shared/format/journal";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { Skeleton } from "@/shared/ui/skeleton";
import { useJournalAudit } from "../api";

const NOMBRE_ENTREES_APERCU = 6;

/** Aperçu des dernières entrées du journal d'audit — connexions, désactivations, décisions sur
 * les comptes (voir app/core/models.py::AuditLogEntry). Un événement daté sur une période, jamais
 * un effectif à un instant T (contrairement aux cartes de statistiques ci-dessus) : ne fait jamais
 * doublon avec elles. "Voir tout le journal" reste la seule vue complète, filtrable. */
export function RecentActivitySection() {
  const { data, isLoading, isError } = useJournalAudit();
  const entrees = (data?.pages[0]?.items ?? []).slice(0, NOMBRE_ENTREES_APERCU);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
          <History className="size-4" />
          Activité récente
        </CardTitle>
        <Button asChild variant="link" size="sm">
          <Link to="/admin/journal-audit">Voir tout le journal</Link>
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : null}
        {isError ? <p className="text-destructive">Impossible de charger le journal.</p> : null}
        {!isLoading && !isError && entrees.length === 0 ? (
          <EmptyState icon={History} message="Aucune activité récente." />
        ) : null}
        {entrees.length > 0 ? (
          <ul className="divide-y">
            {entrees.map((entree) => (
              <li key={entree.id} className="flex items-center justify-between gap-4 py-2 text-sm">
                <div className="flex items-center gap-2">
                  <Badge variant="outline">{libelleActionJournal(entree.action)}</Badge>
                  <span className="text-brand-grey">
                    {libelleTypeRessource(entree.resource_type)}
                  </span>
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {new Date(entree.occurred_at).toLocaleString("fr-FR")}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}
