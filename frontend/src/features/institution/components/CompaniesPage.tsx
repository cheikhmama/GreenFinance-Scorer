import { Building2, Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { CarbonSummary, ScoreSummary } from "@/shared/esg/EsgSummary";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { usePublishedCompaniesForInstitution } from "../api";

/** Catalogue des entreprises publiées, consultable en dehors du contexte d'un projet — jusqu'ici
 * ce catalogue n'était accessible qu'à travers la modale de sélection du périmètre d'un projet
 * (voir ProjectDetailPage), sans possibilité de le parcourir avec le détail ESG/carbone comme
 * côté Chercheur (DonneesPage) ou Investisseur. Même patron que DonneesPage, sans la sélection
 * de comparaison : comparer est un geste d'analyse, pas un geste de décision institutionnelle. */
export function CompaniesPage() {
  const [recherche, setRecherche] = useState("");
  const rechercheDebattue = useDebouncedValue(recherche);
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    usePublishedCompaniesForInstitution({ recherche: rechercheDebattue });

  const entreprises = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Entreprises"
        description="Entreprises publiées — score ESG et émissions Scope 1/2/3, base de tout périmètre de projet."
      />

      <label htmlFor="institution-entreprises-recherche" className="relative block max-w-sm">
        <span className="sr-only">Rechercher une entreprise</span>
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-brand-grey" />
        <Input
          id="institution-entreprises-recherche"
          value={recherche}
          onChange={(event) => setRecherche(event.target.value)}
          placeholder="Rechercher par nom ou secteur"
          className="pl-9"
        />
      </label>

      {isLoading ? <CardListSkeleton /> : null}
      {isError ? <p className="text-destructive">Impossible de charger les entreprises.</p> : null}
      {!isLoading && !isError && entreprises.length === 0 ? (
        <EmptyState icon={Building2} message="Aucune entreprise ne correspond à cette recherche." />
      ) : null}

      <div className="space-y-4">
        {entreprises.map((entreprise) => (
          <Card key={entreprise.id}>
            <CardContent className="space-y-4">
              <div>
                <Link
                  to={`/institution/entreprises/${entreprise.id}`}
                  className="text-base font-semibold text-brand-blue underline-offset-2 hover:underline"
                >
                  {entreprise.name}
                </Link>
                <p className="text-sm text-brand-grey">
                  {entreprise.sector} — {entreprise.country}
                </p>
              </div>
              <ScoreSummary score={entreprise.score} />
              <CarbonSummary carbone={entreprise.carbon} />
            </CardContent>
          </Card>
        ))}
      </div>

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
    </div>
  );
}
