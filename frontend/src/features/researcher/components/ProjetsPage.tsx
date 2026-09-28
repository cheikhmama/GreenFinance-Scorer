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
  date_debut: string | null;
  date_fin_prevue: string | null;
  date_limite: string | null;
}): string | null {
  const morceaux: string[] = [];
  if (projet.date_debut) morceaux.push(`Du ${new Date(projet.date_debut).toLocaleDateString("fr-FR")}`);
  if (projet.date_fin_prevue) morceaux.push(`au ${new Date(projet.date_fin_prevue).toLocaleDateString("fr-FR")}`);
  if (projet.date_limite) {
    morceaux.push(`échéance : ${new Date(projet.date_limite).toLocaleDateString("fr-FR")}`);
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
        eyebrow="Chercheur"
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
                      <p className="font-medium text-brand-blue">{projet.nom}</p>
                      <p className="text-sm text-brand-grey">{projet.institution_email}</p>
                    </div>
                    <Badge variant={variantStatutProjet(projet.statut)}>
                      {libelleStatutProjet(projet.statut)}
                    </Badge>
                  </div>
                  {projet.objectif ? <p className="text-sm text-brand-grey">{projet.objectif}</p> : null}
                  {periode ? <p className="text-xs text-brand-grey">{periode}</p> : null}
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
