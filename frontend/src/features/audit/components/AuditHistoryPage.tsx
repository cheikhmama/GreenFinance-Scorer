import { Link } from "react-router-dom";
import { libelleDecisionAudit } from "@/shared/format/decisionAudit";
import { titreDeclaration } from "@/shared/format/typeRapport";
import { PageShell } from "@/shared/layout/PageShell";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { useAuditHistory } from "../api";

export function AuditHistoryPage() {
  const { data: avis, isLoading, isError } = useAuditHistory();

  return (
    <PageShell
      title="Historique de mes avis"
      description="Dossiers sur lesquels un avis a déjà été rendu."
    >
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Avis rendus</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? <Skeleton className="h-32 w-full" /> : null}
          {isError ? (
            <p className="text-sm text-destructive">Impossible de charger l'historique.</p>
          ) : null}
          {!isLoading && !isError && avis?.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun avis rendu pour l'instant.</p>
          ) : null}
          {avis && avis.length > 0 ? (
            <ul className="divide-y divide-border">
              {avis.map((item) => (
                <li
                  key={item.id}
                  className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0"
                >
                  <div className="min-w-0">
                    <p className="font-medium text-foreground">{item.company_name}</p>
                    <p className="text-sm text-muted-foreground">
                      {titreDeclaration({
                        type: item.report_type,
                        fiscal_year: item.fiscal_year,
                        version: item.report_version,
                      })}
                    </p>
                    <p className="mt-1 text-sm font-medium text-foreground">
                      {libelleDecisionAudit(item.decision)}
                    </p>
                    {item.comment ? (
                      <p className="text-sm text-muted-foreground">{item.comment}</p>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1 text-sm text-muted-foreground">
                    <span>{new Date(item.submitted_at).toLocaleDateString("fr-FR")}</span>
                    <Button asChild variant="ghost" size="sm">
                      <Link to={`/audit/rapports/${item.report_id}`}>Voir le dossier</Link>
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
        </CardContent>
      </Card>
    </PageShell>
  );
}
