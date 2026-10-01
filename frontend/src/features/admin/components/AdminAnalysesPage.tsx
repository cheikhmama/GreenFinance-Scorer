import { FlaskConical } from "lucide-react";
import type { AnalysisStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleStatutAnalyse, variantStatutAnalyse } from "@/shared/format/statutAnalyse";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { useAnalysesAdmin } from "../api";
import { useOngletParametre } from "../useOngletParametre";

const STATUTS: AnalysisStatus[] = ["BROUILLON", "SOUMISE", "VALIDEE", "CORRECTION_DEMANDEE"];

/** Toutes les analyses Chercheur (toutes versions), filtrable par statut — détail derrière
 * "Analyses par statut" / "Corrections demandées" des onglets Chercheur et Institution du tableau
 * de bord. Une ligne = une version précise (Analyse.analyse_precedente_id) : jamais fusionnée
 * avec ses versions précédentes/suivantes. Suivi en lecture seule, le contenu reste privé aux
 * acteurs concernés (Chercheur/Institution). */
export function AdminAnalysesPage() {
  const [statut, setStatut] = useOngletParametre<AnalysisStatus | "">("statut", "");
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useAnalysesAdmin(statut || undefined);

  const analyses = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div className="space-y-8">
      <PageHeader
        title="Analyses"
        description="Toutes les analyses Chercheur, toutes versions, filtrables par statut."
      />
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4">
          <CardTitle>Analyses</CardTitle>
          <Select
            value={statut}
            onChange={(event) => setStatut(event.target.value as AnalysisStatus | "")}
            className="w-56"
          >
            <option value="">Tous les statuts</option>
            {STATUTS.map((valeur) => (
              <option key={valeur} value={valeur}>
                {libelleStatutAnalyse(valeur)}
              </option>
            ))}
          </Select>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading ? <CardListSkeleton count={3} /> : null}
          {isError ? <p className="text-destructive">Impossible de charger les analyses.</p> : null}
          {!isLoading && !isError && analyses.length === 0 ? (
            <EmptyState icon={FlaskConical} message="Aucune analyse pour ce filtre." />
          ) : null}

          {analyses.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Analyse</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead>Chercheur</TableHead>
                  <TableHead>Projet</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>Soumise le</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {analyses.map((analyse) => (
                  <TableRow key={analyse.id}>
                    <TableCell className="font-medium text-brand-blue">{analyse.title}</TableCell>
                    <TableCell>
                      <Badge variant={variantStatutAnalyse(analyse.status)}>
                        {libelleStatutAnalyse(analyse.status)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-brand-grey">{analyse.researcher_email}</TableCell>
                    <TableCell className="text-brand-grey">{analyse.project_name}</TableCell>
                    <TableCell className="tabular-nums">{analyse.version}</TableCell>
                    <TableCell className="text-brand-grey">
                      {analyse.submitted_at
                        ? new Date(analyse.submitted_at).toLocaleDateString("fr-FR")
                        : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
          {analyses.length > 0 && hasNextPage ? (
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
