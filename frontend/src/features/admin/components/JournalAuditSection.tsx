import { Search } from "lucide-react";
import { useState } from "react";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { useJournalAudit } from "../api";

/** Trace des événements de compte et de session (connexion, déconnexion, changement de mot de
 * passe, changement de rôle, désactivation) — voir app/core/models.py::JournalAudit. Ne couvre
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
                placeholder="Filtrer par action (ex. connexion)"
                className="pl-9"
              />
            </label>
            <label htmlFor="journal-type-ressource" className="relative block max-w-xs flex-1">
              <span className="sr-only">Filtrer par type de ressource</span>
              <Input
                id="journal-type-ressource"
                value={typeRessource}
                onChange={(event) => setTypeRessource(event.target.value)}
                placeholder="Filtrer par ressource (ex. Utilisateur)"
              />
            </label>
          </div>
        )}

        {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
        {isError ? <p className="text-destructive">Impossible de charger le journal.</p> : null}
        {!isLoading && !isError && entrees.length === 0 ? (
          <p className="text-brand-grey">Aucune entrée pour ce filtre.</p>
        ) : null}
        {entrees.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-brand-grey">
                  <th className="py-2 pr-4 font-medium">Date</th>
                  <th className="py-2 pr-4 font-medium">Action</th>
                  <th className="py-2 pr-4 font-medium">Ressource</th>
                  <th className="py-2 pr-4 font-medium">Résultat</th>
                  <th className="py-2 font-medium">Détail</th>
                </tr>
              </thead>
              <tbody>
                {entrees.map((entree) => (
                  <tr key={entree.id} className="border-b last:border-0">
                    <td className="py-2 pr-4 whitespace-nowrap">
                      {new Date(entree.date).toLocaleString("fr-FR")}
                    </td>
                    <td className="py-2 pr-4">{entree.action}</td>
                    <td className="py-2 pr-4">{entree.type_ressource}</td>
                    <td className="py-2 pr-4">{entree.resultat}</td>
                    <td className="py-2 text-brand-grey">
                      {entree.ancienne_valeur && entree.nouvelle_valeur
                        ? `${entree.ancienne_valeur} → ${entree.nouvelle_valeur}`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
