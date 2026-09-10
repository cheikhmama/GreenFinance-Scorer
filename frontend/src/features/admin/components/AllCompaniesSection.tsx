import { Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { useAllCompanies, useReactivateCompany, useSuspendCompany } from "../api";

/** Vue de suivi de TOUTES les entreprises pour l'Administrateur — contrairement à
 * PublishableCompaniesSection (uniquement celles prêtes à publier), inclut aussi une entreprise
 * sans aucun rapport et sans compte utilisateur rattaché, avec son statut. Recherche et
 * pagination portées par l'API (GET /admin/entreprises?recherche=&page=&page_size=), même
 * principe "Voir plus" que les autres listes Admin. */
export function AllCompaniesSection() {
  const [recherche, setRecherche] = useState("");
  const rechercheDebattue = useDebouncedValue(recherche);
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useAllCompanies(rechercheDebattue);
  const suspend = useSuspendCompany();
  const reactivate = useReactivateCompany();
  const [actionError, setActionError] = useState<string | null>(null);

  const entreprises = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Toutes les entreprises</CardTitle>
      </CardHeader>
      <CardContent>
        <label htmlFor="toutes-entreprises-recherche" className="relative mb-4 block max-w-sm">
          <span className="sr-only">Rechercher une entreprise</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-brand-grey" />
          <Input
            id="toutes-entreprises-recherche"
            value={recherche}
            onChange={(event) => setRecherche(event.target.value)}
            placeholder="Rechercher par nom, secteur ou pays"
            className="pl-9"
          />
        </label>

        {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
        {isError ? <p className="text-destructive">Impossible de charger la liste.</p> : null}
        {actionError ? <p className="text-sm text-destructive">{actionError}</p> : null}
        {!isLoading && !isError && entreprises.length === 0 ? (
          <p className="text-brand-grey">Aucune entreprise.</p>
        ) : null}
        {entreprises.length > 0 ? (
          <ul className="divide-y">
            {entreprises.map((entreprise) => (
              <li key={entreprise.id} className="flex items-center justify-between gap-4 py-3">
                <div>
                  <p className="text-brand-blue">
                    {entreprise.nom} — {entreprise.secteur} ({entreprise.pays})
                  </p>
                  <p className="text-xs text-brand-grey">
                    {entreprise.nombre_rapports} rapport{entreprise.nombre_rapports > 1 ? "s" : ""}
                  </p>
                  <Link
                    to={`/admin/entreprises/${entreprise.id}/rapports`}
                    className="text-xs text-brand-green underline underline-offset-2"
                  >
                    Voir les rapports
                  </Link>
                </div>
                <div className="flex items-center gap-2">
                  {!entreprise.actif ? <Badge variant="destructive">Suspendue</Badge> : null}
                  {entreprise.dernier_statut_rapport ? (
                    <Badge variant={variantStatutRapport(entreprise.dernier_statut_rapport)}>
                      {libelleStatutRapport(entreprise.dernier_statut_rapport)}
                    </Badge>
                  ) : (
                    <Badge variant="secondary">Aucun rapport</Badge>
                  )}
                  <Badge variant={entreprise.utilisateur_id ? "success" : "outline"}>
                    {entreprise.utilisateur_id ? "Compte lié" : "Sans compte"}
                  </Badge>
                  {entreprise.actif ? (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={suspend.isPending}
                      onClick={() => {
                        setActionError(null);
                        suspend.mutate(entreprise.id, {
                          onError: (err) =>
                            setActionError(
                              err instanceof ApiError ? err.message : "Échec de la suspension.",
                            ),
                        });
                      }}
                    >
                      Suspendre
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={reactivate.isPending}
                      onClick={() => {
                        setActionError(null);
                        reactivate.mutate(entreprise.id, {
                          onError: (err) =>
                            setActionError(
                              err instanceof ApiError ? err.message : "Échec de la réactivation.",
                            ),
                        });
                      }}
                    >
                      Réactiver
                    </Button>
                  )}
                </div>
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
