import { FolderKanban } from "lucide-react";
import type { ProjectStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleStatutProjet, variantStatutProjet } from "@/shared/format/statutProjet";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { useProjectsAdmin } from "../api";
import { useOngletParametre } from "../useOngletParametre";

const STATUTS: ProjectStatus[] = ["OUVERT", "CLOTURE"];

/** Tous les projets Institution, filtrable par statut — détail derrière "Projets ouverts/clôturés"
 * de l'onglet Institution du tableau de bord. Suivi en lecture seule : la composition (chercheurs
 * affectés, périmètre d'entreprises) reste gérée depuis l'espace Institution, jamais ici. */
export function AdminProjetsPage() {
  const [statut, setStatut] = useOngletParametre<ProjectStatus | "">("statut", "");
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useProjectsAdmin(statut || undefined);

  const projets = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Projets"
        description="Tous les projets Institution, filtrables par statut."
      />
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4">
          <CardTitle>Projets</CardTitle>
          <Select
            value={statut}
            onChange={(event) => setStatut(event.target.value as ProjectStatus | "")}
            className="w-48"
          >
            <option value="">Tous les statuts</option>
            {STATUTS.map((valeur) => (
              <option key={valeur} value={valeur}>
                {libelleStatutProjet(valeur)}
              </option>
            ))}
          </Select>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? <CardListSkeleton count={3} /> : null}
          {isError ? <p className="text-destructive">Impossible de charger les projets.</p> : null}
          {!isLoading && !isError && projets.length === 0 ? (
            <EmptyState icon={FolderKanban} message="Aucun projet pour ce filtre." />
          ) : null}

          {projets.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Projet</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead>Institution</TableHead>
                  <TableHead>Chercheurs affectés</TableHead>
                  <TableHead>Échéance</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {projets.map((projet) => (
                  <TableRow key={projet.id}>
                    <TableCell className="font-medium text-brand-blue">{projet.name}</TableCell>
                    <TableCell>
                      <Badge variant={variantStatutProjet(projet.status)}>
                        {libelleStatutProjet(projet.status)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-brand-grey">{projet.institution_email}</TableCell>
                    <TableCell className="tabular-nums">{projet.researcher_count}</TableCell>
                    <TableCell className="text-brand-grey">
                      {projet.deadline
                        ? new Date(projet.deadline).toLocaleDateString("fr-FR")
                        : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
          {projets.length > 0 && hasNextPage ? (
            <Button
              variant="outline"
              size="sm"
              disabled={isFetchingNextPage}
              onClick={() => fetchNextPage()}
            >
              {isFetchingNextPage ? "Chargement..." : "Voir plus"}
            </Button>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
