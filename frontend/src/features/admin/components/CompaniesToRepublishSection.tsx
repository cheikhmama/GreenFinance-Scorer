import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { ApiError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { useCompaniesToRepublish, usePublishCompany } from "../api";

/** Entreprises déjà publiées dont un rapport a été validé après la dernière publication : leur
 * fiche publique ne reflète plus le dernier état validé — voir
 * app/admin/review_queue.py::lister_entreprises_a_republier. Republier utilise le même geste que
 * publier une première fois (POST .../publier, voir publier_entreprise), pas d'action distincte.
 * Affichée dans son propre onglet (AdminCompaniesPage) : jamais mélangée aux entreprises
 * inscrites ou publiables, chacune répondant à un critère distinct. */
export function CompaniesToRepublishSection() {
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useCompaniesToRepublish();
  const publish = usePublishCompany();
  const [error, setError] = useState<string | null>(null);

  const entreprises = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Card className="border-amber-300">
      <CardHeader>
        <CardTitle className="text-base text-amber-700">Demandes de republication</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? <CardListSkeleton count={2} /> : null}
        {isError ? <p className="text-destructive">Impossible de charger la liste.</p> : null}
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {!isLoading && !isError && entreprises.length === 0 ? (
          <EmptyState icon={RefreshCw} message="Aucune entreprise en attente de republication." />
        ) : null}
        {entreprises.length > 0 ? (
          <ul className="divide-y">
            {entreprises.map((entreprise) => (
              <li key={entreprise.id} className="flex items-center justify-between gap-4 py-3">
                <span className="text-brand-blue">
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
                          err instanceof ApiError ? err.message : "Échec de la republication.",
                        ),
                    });
                  }}
                >
                  Republier
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
