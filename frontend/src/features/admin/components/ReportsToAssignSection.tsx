import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Select } from "@/shared/ui/select";
import { useAssignReport, useReportsToAssign, useUtilisateursSelectionnables } from "../api";
import { Role } from "../schemas";

/** File d'affectation (Phase 4 §4.4) — un rapport n'apparaît ici que l'extraction terminée
 * (app/admin/review_queue.py::lister_rapports_a_affecter). Auditeur choisi parmi les comptes
 * déjà enregistrés, jamais une saisie libre (règle déjà validée pour ce projet). */
export function ReportsToAssignSection() {
  const { data: rapports, isLoading, isError } = useReportsToAssign();
  const { data: auditeurs } = useUtilisateursSelectionnables(Role.AUDITEUR);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Rapports à affecter</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
        {isError ? <p className="text-destructive">Impossible de charger la file.</p> : null}
        {!isLoading && !isError && rapports?.length === 0 ? (
          <p className="text-brand-grey">Aucun rapport en attente d'affectation.</p>
        ) : null}
        {rapports && rapports.length > 0 ? (
          <ul className="divide-y">
            {rapports.map((rapport) => (
              <LigneAffectation
                key={rapport.id}
                rapportId={rapport.id}
                type={rapport.type}
                auditeurs={auditeurs ?? []}
              />
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}

function LigneAffectation({
  rapportId,
  type,
  auditeurs,
}: {
  rapportId: string;
  type: string;
  auditeurs: { id: string; email: string }[];
}) {
  const assign = useAssignReport(rapportId);
  const [auditeurId, setAuditeurId] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleAssign() {
    if (!auditeurId) return;
    setError(null);
    assign.mutate(
      { auditeur_id: auditeurId },
      {
        onError: (err) => {
          setError(err instanceof ApiError ? err.message : "Échec de l'affectation.");
        },
      },
    );
  }

  return (
    <li className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <Link
          to={`/admin/rapports/${rapportId}`}
          className="font-medium text-brand-blue underline underline-offset-2"
        >
          {type}
        </Link>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
      </div>
      <div className="flex items-center gap-2">
        <Select value={auditeurId} onChange={(e) => setAuditeurId(e.target.value)} className="w-56">
          <option value="">Choisir un auditeur…</option>
          {auditeurs.map((auditeur) => (
            <option key={auditeur.id} value={auditeur.id}>
              {auditeur.email}
            </option>
          ))}
        </Select>
        <Button size="sm" disabled={!auditeurId || assign.isPending} onClick={handleAssign}>
          {assign.isPending ? "Affectation..." : "Affecter"}
        </Button>
      </div>
    </li>
  );
}
