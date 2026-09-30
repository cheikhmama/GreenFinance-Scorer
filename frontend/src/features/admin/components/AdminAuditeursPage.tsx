import { ClipboardCheck, Search } from "lucide-react";
import { useState } from "react";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { useAuditorWorkload } from "../api";

/** Charge de travail par Auditeur actif — détail derrière "Dossiers affectés" de l'onglet Auditeur
 * du tableau de bord (indicateur → liste filtrée). Suivi en lecture seule : la réaffectation d'un
 * dossier se fait depuis la fiche du rapport concerné (/admin/rapports/:id), pas ici. */
export function AdminAuditeursPage() {
  const [recherche, setRecherche] = useState("");
  const rechercheDebattue = useDebouncedValue(recherche);
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useAuditorWorkload(rechercheDebattue);

  const auditeurs = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Auditeurs"
        description="Charge de travail par Auditeur actif : dossiers affectés, en retard et avis rendus."
      />
      <Card>
        <CardHeader>
          <CardTitle>Charge par Auditeur</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <label htmlFor="auditeurs-recherche" className="relative block max-w-sm">
            <span className="sr-only">Rechercher un auditeur par e-mail</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-brand-grey" />
            <Input
              id="auditeurs-recherche"
              value={recherche}
              onChange={(event) => setRecherche(event.target.value)}
              placeholder="Rechercher par e-mail"
              className="pl-9"
            />
          </label>

          {isLoading ? <CardListSkeleton count={3} /> : null}
          {isError ? <p className="text-destructive">Impossible de charger la charge des auditeurs.</p> : null}
          {!isLoading && !isError && auditeurs.length === 0 ? (
            <EmptyState icon={ClipboardCheck} message="Aucun auditeur actif pour ce filtre." />
          ) : null}

          {auditeurs.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Auditeur</TableHead>
                  <TableHead>Dossiers affectés</TableHead>
                  <TableHead>Dont en retard</TableHead>
                  <TableHead>Avis rendus (total)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {auditeurs.map((auditeur) => (
                  <TableRow key={auditeur.auditor_id}>
                    <TableCell className="font-medium text-brand-blue">{auditeur.email}</TableCell>
                    <TableCell className="tabular-nums">{auditeur.assigned_reports}</TableCell>
                    <TableCell>
                      {auditeur.overdue_reports > 0 ? (
                        <Badge variant="warning">{auditeur.overdue_reports}</Badge>
                      ) : (
                        <span className="tabular-nums text-brand-grey">0</span>
                      )}
                    </TableCell>
                    <TableCell className="tabular-nums text-brand-grey">{auditeur.opinions_submitted}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
          {auditeurs.length > 0 && hasNextPage ? (
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
