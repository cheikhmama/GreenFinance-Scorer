import { Search, Wallet } from "lucide-react";
import { useState } from "react";
import { formatMontant } from "@/shared/format/etatPosition";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { usePortfoliosAdmin } from "../api";

/** Tous les portefeuilles non archivés, tous Investisseurs confondus — détail derrière
 * "Portefeuilles non archivés" de l'onglet Investisseur du tableau de bord. Suivi en lecture
 * seule : la composition détaillée (positions) reste privée à son titulaire, jamais exposée ici
 * au-delà du nombre de positions et du montant total dans la devise de référence. */
export function AdminPortefeuillesPage() {
  const [recherche, setRecherche] = useState("");
  const rechercheDebattue = useDebouncedValue(recherche);
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    usePortfoliosAdmin(rechercheDebattue);

  const portefeuilles = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Portefeuilles"
        description="Tous les portefeuilles non archivés, tous Investisseurs confondus."
      />
      <Card>
        <CardHeader>
          <CardTitle>Portefeuilles</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <label htmlFor="portefeuilles-recherche" className="relative block max-w-sm">
            <span className="sr-only">Rechercher par nom de portefeuille ou e-mail</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-brand-grey" />
            <Input
              id="portefeuilles-recherche"
              value={recherche}
              onChange={(event) => setRecherche(event.target.value)}
              placeholder="Rechercher par nom ou e-mail"
              className="pl-9"
            />
          </label>

          {isLoading ? <CardListSkeleton count={3} /> : null}
          {isError ? (
            <p className="text-destructive">Impossible de charger les portefeuilles.</p>
          ) : null}
          {!isLoading && !isError && portefeuilles.length === 0 ? (
            <EmptyState icon={Wallet} message="Aucun portefeuille pour ce filtre." />
          ) : null}

          {portefeuilles.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Portefeuille</TableHead>
                  <TableHead>Titulaire</TableHead>
                  <TableHead>Positions</TableHead>
                  <TableHead>Montant total</TableHead>
                  <TableHead>Créé le</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {portefeuilles.map((portefeuille) => (
                  <TableRow key={portefeuille.id}>
                    <TableCell className="font-medium text-brand-blue">
                      {portefeuille.name}
                    </TableCell>
                    <TableCell className="text-brand-grey">{portefeuille.investor_email}</TableCell>
                    <TableCell className="tabular-nums">{portefeuille.position_count}</TableCell>
                    <TableCell className="tabular-nums">
                      {formatMontant(portefeuille.total_amount, portefeuille.reference_currency)}
                    </TableCell>
                    <TableCell className="text-brand-grey">
                      {new Date(portefeuille.created_at).toLocaleDateString("fr-FR")}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
          {portefeuilles.length > 0 && hasNextPage ? (
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
