import { Scale, Search } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { CarbonSummary, ScoreSummary } from "@/shared/esg/EsgSummary";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { usePublishedCompanies } from "../api";

/** Liste des entreprises publiées, avec sélection multiple pour la comparaison (au moins 2,
 * voir GET /investor/comparaison). Pagination "Voir plus" (même pattern que UsersSection). */
export function CompaniesPage() {
  const [recherche, setRecherche] = useState("");
  const [selection, setSelection] = useState<string[]>([]);
  const rechercheDebattue = useDebouncedValue(recherche);
  const navigate = useNavigate();
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    usePublishedCompanies({ recherche: rechercheDebattue });

  const entreprises = data?.pages.flatMap((page) => page.items) ?? [];

  function toggleSelection(id: string) {
    setSelection((current) =>
      current.includes(id) ? current.filter((v) => v !== id) : [...current, id],
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Investisseur"
        title="Entreprises publiées"
        description="Score ESG et émissions Scope 1/2/3 des entreprises dont les données ont été validées et publiées."
        action={
          selection.length >= 2 ? (
            <Button onClick={() => navigate(`/investor/comparaison?ids=${selection.join(",")}`)}>
              <Scale className="mr-2 size-4" />
              Comparer ({selection.length})
            </Button>
          ) : undefined
        }
      />

      <label htmlFor="entreprises-recherche" className="relative block max-w-sm">
        <span className="sr-only">Rechercher une entreprise</span>
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-brand-grey" />
        <Input
          id="entreprises-recherche"
          value={recherche}
          onChange={(event) => setRecherche(event.target.value)}
          placeholder="Rechercher par nom ou secteur"
          className="pl-9"
        />
      </label>

      {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
      {isError ? <p className="text-destructive">Impossible de charger les entreprises.</p> : null}
      {!isLoading && !isError && entreprises.length === 0 ? (
        <p className="text-brand-grey">Aucune entreprise publiée pour l'instant.</p>
      ) : null}

      <div className="space-y-4">
        {entreprises.map((entreprise) => (
          <Card key={entreprise.id}>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <label className="mt-1 flex items-center gap-2">
                    <span className="sr-only">Sélectionner {entreprise.nom} pour comparaison</span>
                    <input
                      type="checkbox"
                      checked={selection.includes(entreprise.id)}
                      onChange={() => toggleSelection(entreprise.id)}
                    />
                  </label>
                  <div>
                    <Link
                      to={`/investor/entreprises/${entreprise.id}`}
                      className="text-base font-semibold text-brand-blue underline-offset-2 hover:underline"
                    >
                      {entreprise.nom}
                    </Link>
                    <p className="text-sm text-brand-grey">
                      {entreprise.secteur} — {entreprise.pays}
                    </p>
                  </div>
                </div>
                {entreprise.montant_minimum_investissement !== null ? (
                  <Badge variant="outline">
                    Minimum {entreprise.montant_minimum_investissement.toLocaleString("fr-FR")}
                  </Badge>
                ) : null}
              </div>
              <ScoreSummary score={entreprise.score} />
              <CarbonSummary carbone={entreprise.carbone} />
            </CardContent>
          </Card>
        ))}
      </div>

      {entreprises.length > 0 && hasNextPage ? (
        <Button variant="outline" size="sm" disabled={isFetchingNextPage} onClick={() => fetchNextPage()}>
          {isFetchingNextPage ? "Chargement..." : "Voir plus"}
        </Button>
      ) : null}
    </div>
  );
}
