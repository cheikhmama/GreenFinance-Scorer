import { Building2, Scale, Search } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CarbonSummary, ScoreSummary } from "@/shared/esg/EsgSummary";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { MAX_ENTREPRISES_COMPARAISON, usePublishedCompaniesForResearcher } from "../api";

/** Liste des entreprises publiées — données de base sur lesquelles construire une analyse
 * (voir AnalysesPage). Sélection multiple pour comparaison, même principe que
 * features/investor/components/CompaniesPage.tsx. */
export function DonneesPage() {
  const [recherche, setRecherche] = useState("");
  const [selection, setSelection] = useState<string[]>([]);
  const rechercheDebattue = useDebouncedValue(recherche);
  const navigate = useNavigate();
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    usePublishedCompaniesForResearcher({ recherche: rechercheDebattue });

  const entreprises = data?.pages.flatMap((page) => page.items) ?? [];

  function toggleSelection(id: string) {
    setSelection((current) => {
      if (current.includes(id)) return current.filter((v) => v !== id);
      // Plafond serveur (app/investor/entreprises.py::_MAX_ENTREPRISES_COMPARAISON) — refusé ici
      // plutôt que via une erreur générique après avoir déjà cliqué sur « Comparer ».
      if (current.length >= MAX_ENTREPRISES_COMPARAISON) return current;
      return [...current, id];
    });
  }

  const plafondAtteint = selection.length >= MAX_ENTREPRISES_COMPARAISON;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Chercheur"
        title="Données"
        description="Entreprises publiées — score ESG et émissions Scope 1/2/3, base de toute analyse."
        action={
          selection.length >= 2 ? (
            <Button onClick={() => navigate(`/researcher/comparaison?ids=${selection.join(",")}`)}>
              <Scale className="mr-2 size-4" />
              Comparer ({selection.length})
            </Button>
          ) : undefined
        }
      />

      <label htmlFor="donnees-recherche" className="relative block max-w-sm">
        <span className="sr-only">Rechercher une entreprise</span>
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-brand-grey" />
        <Input
          id="donnees-recherche"
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
      {plafondAtteint ? (
        <p className="text-sm text-brand-grey">
          Maximum {MAX_ENTREPRISES_COMPARAISON} entreprises pour une comparaison — décochez-en une
          pour en choisir une autre.
        </p>
      ) : null}

      <div className="space-y-4">
        {entreprises.map((entreprise) => {
          const selectionnee = selection.includes(entreprise.id);
          return (
            <Card key={entreprise.id}>
              <CardContent className="space-y-4">
                <div className="flex items-start gap-3">
                  <label className="mt-1 flex items-center gap-2">
                    <span className="sr-only">Sélectionner {entreprise.name} pour comparaison</span>
                    <input
                      type="checkbox"
                      checked={selectionnee}
                      disabled={!selectionnee && plafondAtteint}
                      onChange={() => toggleSelection(entreprise.id)}
                    />
                  </label>
                  <div>
                    <Link
                      to={`/researcher/entreprises/${entreprise.id}`}
                      className="text-base font-semibold text-brand-blue underline-offset-2 hover:underline"
                    >
                      {entreprise.name}
                    </Link>
                    <p className="text-sm text-brand-grey">
                      {entreprise.sector} — {entreprise.country}
                    </p>
                  </div>
                </div>
                <ScoreSummary score={entreprise.score} />
                <CarbonSummary carbone={entreprise.carbon} />
              </CardContent>
            </Card>
          );
        })}
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
