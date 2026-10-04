import { FlaskConical } from "lucide-react";
import { Link } from "react-router-dom";
import { libelleStatutAnalyse, variantStatutAnalyse } from "@/shared/format/statutAnalyse";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { PageHeader } from "@/shared/ui/page-header";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { useMyAnalysesForInstitution } from "../api";

/** Vue d'ensemble des analyses reçues, tous projets confondus — comble le manque d'une liste
 * globale (ProjectDetailPage n'en montre qu'un projet à la fois). Les analyses SOUMISE (en
 * attente de décision) remontent toujours en premier, c'est le seul tri qui compte ici. */
export function AnalysesPage() {
  const { data: analyses, isLoading, isError } = useMyAnalysesForInstitution();
  const aDecider = analyses?.filter((a) => a.status === "SOUMISE").length ?? 0;

  const triees = [...(analyses ?? [])].sort((a, b) => {
    if (a.status === "SOUMISE" && b.status !== "SOUMISE") return -1;
    if (a.status !== "SOUMISE" && b.status === "SOUMISE") return 1;
    return b.created_at.localeCompare(a.created_at);
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analyses"
        description="Toutes les analyses reçues de vos chercheurs, tous projets confondus."
      />

      {aDecider > 0 ? (
        <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          {aDecider} analyse{aDecider > 1 ? "s" : ""} en attente de votre décision.
        </p>
      ) : null}

      {isLoading ? <CardListSkeleton /> : null}
      {isError ? <p className="text-destructive">Impossible de charger les analyses.</p> : null}
      {!isLoading && !isError && triees.length === 0 ? (
        <EmptyState
          icon={FlaskConical}
          message="Aucune analyse reçue pour l'instant — elles apparaîtront ici dès qu'un chercheur affecté à l'un de vos projets en soumettra une."
        />
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        {triees.map((analyse) => (
          <Link key={analyse.id} to={`/institution/analyses/${analyse.id}`}>
            <Card className="h-full transition hover:border-brand-green hover:shadow-md">
              <CardContent className="space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <p className="font-medium text-foreground">{analyse.title}</p>
                  <Badge variant={variantStatutAnalyse(analyse.status)}>
                    {libelleStatutAnalyse(analyse.status)}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  {analyse.project_name} — version {analyse.version}
                </p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
