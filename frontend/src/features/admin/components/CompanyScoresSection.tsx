import { BarChart3 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { Input } from "@/shared/ui/input";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { useCompaniesWithScore } from "../api";

function formatScore(valeur: number | null | undefined): string {
  return valeur !== null && valeur !== undefined ? valeur.toFixed(1) : "—";
}

/** Détail derrière les cartes de performance ESG (indicateur → liste filtrée) — chaque entreprise
 * publiée avec son score admissible, jamais 0 quand absent. Filtrable par secteur/pays (texte
 * libre : pas de liste de valeurs distinctes exposée côté API, un filtre simple suffit ici). */
export function CompanyScoresSection() {
  const [secteur, setSecteur] = useState("");
  const [pays, setPays] = useState("");
  const secteurDebattu = useDebouncedValue(secteur);
  const paysDebattu = useDebouncedValue(pays);
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useCompaniesWithScore(secteurDebattu, paysDebattu);

  const entreprises = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Scores ESG par entreprise</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-3">
          <Input
            value={secteur}
            onChange={(event) => setSecteur(event.target.value)}
            placeholder="Filtrer par secteur"
            className="max-w-xs"
          />
          <Input
            value={pays}
            onChange={(event) => setPays(event.target.value)}
            placeholder="Filtrer par pays"
            className="max-w-xs"
          />
        </div>

        {isLoading ? <CardListSkeleton count={3} /> : null}
        {isError ? <p className="text-destructive">Impossible de charger les scores.</p> : null}
        {!isLoading && !isError && entreprises.length === 0 ? (
          <EmptyState icon={BarChart3} message="Aucune entreprise pour ce filtre." />
        ) : null}

        {entreprises.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Entreprise</TableHead>
                <TableHead>Secteur</TableHead>
                <TableHead>Pays</TableHead>
                <TableHead>Global</TableHead>
                <TableHead>E</TableHead>
                <TableHead>S</TableHead>
                <TableHead>G</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entreprises.map((entreprise) => (
                <TableRow key={entreprise.id}>
                  <TableCell>
                    <Link
                      to={`/admin/entreprises/${entreprise.id}`}
                      className="font-medium text-brand-blue hover:underline"
                    >
                      {entreprise.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-brand-grey">{entreprise.sector}</TableCell>
                  <TableCell className="text-brand-grey">{entreprise.country}</TableCell>
                  <TableCell className="font-semibold tabular-nums text-brand-blue">
                    {formatScore(entreprise.global_score)}
                  </TableCell>
                  <TableCell className="tabular-nums text-brand-grey">
                    {formatScore(entreprise.environmental_score)}
                  </TableCell>
                  <TableCell className="tabular-nums text-brand-grey">
                    {formatScore(entreprise.social_score)}
                  </TableCell>
                  <TableCell className="tabular-nums text-brand-grey">
                    {formatScore(entreprise.governance_score)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : null}
        {entreprises.length > 0 && hasNextPage ? (
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
  );
}
