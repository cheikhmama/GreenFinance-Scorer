import { History } from "lucide-react";
import { useState } from "react";
import {
  libelleActionJournal,
  libelleResultatJournal,
  libelleTypeRessource,
  libelleValeurJournal,
  OPTIONS_ACTIONS_JOURNAL,
  OPTIONS_TYPES_RESSOURCE,
} from "@/shared/format/journal";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { Select } from "@/shared/ui/select";
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
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useJournalAudit({
      concerne_id: concerneId,
      action: action || undefined,
      type_ressource: typeRessource || undefined,
    });

  const entrees = data?.pages.flatMap((page) => page.items) ?? [];
  // Seuls les changements (rôle, état du compte, e-mail) ont un avant/après : une colonne
  // toujours vide n'est affichée que si au moins une entrée chargée en a un.
  const avecDetail = entrees.some((entree) => entree.old_value && entree.new_value);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Journal d'audit</CardTitle>
      </CardHeader>
      <CardContent>
        {concerneId ? null : (
          <div className="mb-4 flex flex-wrap gap-3">
            <label htmlFor="journal-action" className="block w-full max-w-xs">
              <span className="sr-only">Filtrer par action</span>
              <Select
                id="journal-action"
                value={action}
                onChange={(event) => setAction(event.target.value)}
              >
                <option value="">Toutes les actions</option>
                {OPTIONS_ACTIONS_JOURNAL.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </label>
            <label htmlFor="journal-type-ressource" className="block w-full max-w-56">
              <span className="sr-only">Filtrer par type de ressource</span>
              <Select
                id="journal-type-ressource"
                value={typeRessource}
                onChange={(event) => setTypeRessource(event.target.value)}
              >
                <option value="">Toutes les ressources</option>
                {OPTIONS_TYPES_RESSOURCE.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
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
                <TableHead>Par</TableHead>
                <TableHead>Ressource</TableHead>
                <TableHead>Résultat</TableHead>
                {avecDetail ? <TableHead>Détail</TableHead> : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {entrees.map((entree) => (
                <TableRow key={entree.id}>
                  <TableCell className="whitespace-nowrap">
                    {new Date(entree.occurred_at).toLocaleString("fr-FR")}
                  </TableCell>
                  <TableCell>{libelleActionJournal(entree.action)}</TableCell>
                  <TableCell>
                    {entree.actor_name || entree.actor_email ? (
                      <span title={entree.actor_email ?? undefined}>
                        {entree.actor_name ?? entree.actor_email}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">Anonyme</span>
                    )}
                  </TableCell>
                  <TableCell>{libelleTypeRessource(entree.resource_type)}</TableCell>
                  <TableCell>{libelleResultatJournal(entree.result)}</TableCell>
                  {avecDetail ? (
                    <TableCell className="text-muted-foreground">
                      {entree.old_value && entree.new_value
                        ? `${libelleValeurJournal(entree.old_value)} → ${libelleValeurJournal(entree.new_value)}`
                        : "—"}
                    </TableCell>
                  ) : null}
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
