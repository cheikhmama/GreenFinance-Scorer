import { useSearchParams } from "react-router-dom";
import { formatScore } from "@/shared/format/etatPosition";
import { libellePays } from "@/shared/format/pays";
import { Card, CardContent } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { useCompareCompaniesForResearcher } from "../api";

export function ComparisonPage() {
  const [searchParams] = useSearchParams();
  const entrepriseIds = (searchParams.get("ids") ?? "").split(",").filter(Boolean);
  const { data: entreprises, isLoading, isError } = useCompareCompaniesForResearcher(entrepriseIds);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Comparaison"
        description="Score ESG et émissions Scope 1/2/3, côte à côte — base d'une analyse."
      />

      {entrepriseIds.length < 2 ? (
        <p className="text-muted-foreground">
          Sélectionne au moins deux entreprises depuis « Données » pour les comparer.
        </p>
      ) : null}
      {isLoading ? <CardListSkeleton count={2} /> : null}
      {isError ? <p className="text-destructive">Impossible de charger la comparaison.</p> : null}

      {entreprises && entreprises.length >= 2 ? (
        <Card>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Critère</TableHead>
                  {entreprises.map((entreprise) => (
                    <TableHead key={entreprise.id} className="text-foreground">
                      {entreprise.name}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                <Ligne titre="Secteur" entreprises={entreprises} render={(e) => e.sector} />
                <Ligne
                  titre="Pays"
                  entreprises={entreprises}
                  render={(e) => libellePays(e.country)}
                />
                <Ligne
                  titre="Score global"
                  entreprises={entreprises}
                  render={(e) => formatScore(e.score.global_score)}
                />
                <Ligne
                  titre="Environnement (E)"
                  entreprises={entreprises}
                  render={(e) => formatScore(e.score.environmental_score)}
                />
                <Ligne
                  titre="Social (S)"
                  entreprises={entreprises}
                  render={(e) => formatScore(e.score.social_score)}
                />
                <Ligne
                  titre="Gouvernance (G)"
                  entreprises={entreprises}
                  render={(e) => formatScore(e.score.governance_score)}
                />
                <Ligne
                  titre="Scope 1 (tCO2e)"
                  entreprises={entreprises}
                  render={(e) => e.carbon.scope_1?.toLocaleString("fr-FR") ?? "—"}
                />
                <Ligne
                  titre="Scope 2, market-based (tCO2e)"
                  entreprises={entreprises}
                  render={(e) => e.carbon.scope_2_market_based?.toLocaleString("fr-FR") ?? "—"}
                />
                <Ligne
                  titre="Scope 2, location-based (tCO2e)"
                  entreprises={entreprises}
                  render={(e) => e.carbon.scope_2_location_based?.toLocaleString("fr-FR") ?? "—"}
                />
                <Ligne
                  titre="Scope 3 (tCO2e)"
                  entreprises={entreprises}
                  render={(e) => e.carbon.scope_3?.toLocaleString("fr-FR") ?? "—"}
                />
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function Ligne<T>({
  titre,
  entreprises,
  render,
}: {
  titre: string;
  entreprises: T[];
  render: (entreprise: T) => string;
}) {
  return (
    <TableRow>
      <TableCell className="font-medium text-muted-foreground">{titre}</TableCell>
      {entreprises.map((entreprise, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: lignes stables, une seule mise à jour par rendu
        <TableCell key={index}>{render(entreprise)}</TableCell>
      ))}
    </TableRow>
  );
}
