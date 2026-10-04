import { CheckCircle2, Search } from "lucide-react";
import { useState } from "react";
import { ApiError } from "@/shared/api/errors";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { Input } from "@/shared/ui/input";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { usePublishableCompanies, usePublishCompany } from "../api";

/** Entreprises ayant au moins un rapport validé, pas encore publiées — publier est un geste
 * distinct de valider (voir app/admin/review_queue.py::publier_entreprise).
 *
 * Recherche et pagination sont portées par l'API (GET /admin/entreprises/publiables?recherche=&
 * page=&page_size=) : 3 entreprises chargées au départ, "Voir plus" charge 3 entreprises de plus
 * depuis la base à chaque clic, jusqu'à épuisement de la liste pour la recherche en cours. */
export function PublishableCompaniesSection() {
  const [recherche, setRecherche] = useState("");
  const rechercheDebattue = useDebouncedValue(recherche);
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    usePublishableCompanies(rechercheDebattue);
  const publish = usePublishCompany();
  const [error, setError] = useState<string | null>(null);

  const entreprises = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Entreprises publiables</CardTitle>
      </CardHeader>
      <CardContent>
        <label htmlFor="entreprises-recherche" className="relative mb-4 block max-w-sm">
          <span className="sr-only">Rechercher une entreprise</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            id="entreprises-recherche"
            value={recherche}
            onChange={(event) => setRecherche(event.target.value)}
            placeholder="Rechercher par nom, secteur ou pays"
            className="pl-9"
          />
        </label>

        {isLoading ? <CardListSkeleton count={3} /> : null}
        {isError ? <p className="text-destructive">Impossible de charger la liste.</p> : null}
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {!isLoading && !isError && entreprises.length === 0 ? (
          <EmptyState icon={CheckCircle2} message="Aucune entreprise en attente de publication." />
        ) : null}
        {entreprises.length > 0 ? (
          <ul className="divide-y">
            {entreprises.map((entreprise) => (
              <li key={entreprise.id} className="flex items-center justify-between gap-4 py-3">
                <span className="text-foreground">
                  {entreprise.name} — {entreprise.sector}
                </span>
                <Button
                  size="sm"
                  disabled={publish.isPending}
                  onClick={() => {
                    setError(null);
                    publish.mutate(entreprise.id, {
                      onError: (err) =>
                        setError(
                          err instanceof ApiError ? err.message : "Échec de la publication.",
                        ),
                    });
                  }}
                >
                  Publier
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
        {entreprises.length > 0 && hasNextPage ? (
          <div className="mt-3">
            <Button
              variant="outline"
              size="sm"
              disabled={isFetchingNextPage}
              onClick={() => fetchNextPage()}
            >
              {isFetchingNextPage ? "Chargement..." : "Voir plus"}
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
