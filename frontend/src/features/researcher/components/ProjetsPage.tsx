import { FolderKanban } from "lucide-react";
import { Link } from "react-router-dom";
import { libelleStatutProjet, variantStatutProjet } from "@/shared/format/statutProjet";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { PageHeader } from "@/shared/ui/page-header";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { useMyAssignedProjects } from "../api";

function formatPeriode(projet: {
  start_date: string | null;
  planned_end_date: string | null;
  deadline: string | null;
}): string | null {
  const morceaux: string[] = [];
  if (projet.start_date)
    morceaux.push(`Du ${new Date(projet.start_date).toLocaleDateString("fr-FR")}`);
  if (projet.planned_end_date)
    morceaux.push(`au ${new Date(projet.planned_end_date).toLocaleDateString("fr-FR")}`);
  if (projet.deadline) {
    morceaux.push(`échéance : ${new Date(projet.deadline).toLocaleDateString("fr-FR")}`);
  }
  return morceaux.length > 0 ? morceaux.join(" — ") : null;
}

/** Projets sur lesquels le Chercheur est affecté — objectif, période et échéance viennent
 * directement de l'Institution (voir app/institution/models.py::Projet), jamais éditables ici. */
export function ProjetsPage() {
  const { data: projets, isLoading, isError } = useMyAssignedProjects();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mes projets"
        description="Projets qui vous sont affectés — objectif, échéances, périmètre et documents autorisés."
      />

      {isLoading ? <CardListSkeleton /> : null}
      {isError ? <p className="text-destructive">Impossible de charger les projets.</p> : null}
      {!isLoading && !isError && projets?.length === 0 ? (
        <EmptyState
          icon={FolderKanban}
          message="Aucun projet ne vous est encore affecté — une institution doit d'abord vous inviter puis vous affecter à un projet."
        />
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        {projets?.map((projet) => {
          const periode = formatPeriode(projet);
          return (
            <Link key={projet.id} to={`/researcher/projets/${projet.id}`}>
              <Card className="h-full transition hover:border-brand-green hover:shadow-md">
                <CardContent className="space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-foreground">{projet.name}</p>
                      <p className="text-sm text-muted-foreground">{projet.institution_email}</p>
                    </div>
                    <Badge variant={variantStatutProjet(projet.status)}>
                      {libelleStatutProjet(projet.status)}
                    </Badge>
                  </div>
                  {projet.objective ? (
                    <p className="text-sm text-muted-foreground">{projet.objective}</p>
                  ) : null}
                  {periode ? <p className="text-xs text-muted-foreground">{periode}</p> : null}
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
