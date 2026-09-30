import { History, Search } from "lucide-react";
import { useState } from "react";
import {
  libelleActionJournal,
  libelleResultatJournal,
  libelleTypeRessource,
  libelleValeurJournal,
} from "@/shared/format/journal";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { Input } from "@/shared/ui/input";
import { Skeleton } from "@/shared/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { useJournalAudit } from "../api";

/** Trace des événements de compte et de session (connexion, déconnexion, changement de mot de
 * passe, changement de rôle, désactivation) — voir app/core/models.py::AuditLogEntry. Ne couvre
 * pas les décisions métier (affectation, validation, rejet), déjà notifiées à l'entreprise
 * concernée et visibles dans l'historique de son rapport. */
export function JournalAuditSection({ concerneId }: { concerneId?: string }) {
  const [action, setAction] = useState("");
  const [typeRessource, setTypeRessource] = useState("");
  const actionDebattue = useDebouncedValue(action);
  const typeRessourceDebattu = useDebouncedValue(typeRessource);
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useJournalAudit({
      concerne_id: concerneId,
      action: actionDebattue || undefined,
      type_ressource: typeRessourceDebattu || undefined,
    });

  const entrees = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Journal d'audit</CardTitle>
      </CardHeader>
      <CardContent>
        {concerneId ? null : (
          <div className="mb-4 flex flex-wrap gap-3">
            <label htmlFor="journal-action" className="relative block max-w-xs flex-1">
              <span className="sr-only">Filtrer par action</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-brand-grey" />
              <Input
                id="journal-action"
                value={action}
                onChange={(event) => setAction(event.target.value)}
                placeholder="Filtrer par action (ex. login)"
                className="pl-9"
              />
            </label>
            <label htmlFor="journal-type-ressource" className="relative block max-w-xs flex-1">
              <span className="sr-only">Filtrer par type de ressource</span>
              <Input
                id="journal-type-ressource"
                value={typeRessource}
                onChange={(event) => setTypeRessource(event.target.value)}
                placeholder="Filtrer par ressource (ex. User)"
              />
            </label>
          </div>
        )}

        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : null}
        {isError ? <p className="text-destructive">Impossible de charger le journal.</p> : null}
        {!isLoading && !isError && entrees.length === 0 ? (
          <EmptyState icon={History} message="Aucune entrée pour ce filtre." />
        ) : null}
        {entrees.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Ressource</TableHead>
                <TableHead>Résultat</TableHead>
                <TableHead>Détail</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entrees.map((entree) => (
                <TableRow key={entree.id}>
                  <TableCell className="whitespace-nowrap">
                    {new Date(entree.occurred_at).toLocaleString("fr-FR")}
                  </TableCell>
                  <TableCell>{libelleActionJournal(entree.action)}</TableCell>
                  <TableCell>{libelleTypeRessource(entree.resource_type)}</TableCell>
                  <TableCell>{libelleResultatJournal(entree.result)}</TableCell>
                  <TableCell className="text-brand-grey">
                    {entree.old_value && entree.new_value
                      ? `${libelleValeurJournal(entree.old_value)} → ${libelleValeurJournal(entree.new_value)}`
                      : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : null}
        {entrees.length > 0 && hasNextPage ? (
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
