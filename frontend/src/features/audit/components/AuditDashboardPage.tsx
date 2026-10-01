import { Link } from "react-router-dom";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { useAssignedReports } from "../api";

/** Espace Auditeur réel (Phase 4 §4.5) — dossiers affectés, en attente d'avis. */
export function AuditDashboardPage() {
  const { data: dossiers, isLoading, isError } = useAssignedReports();

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Auditeur"
        title="Dossiers affectés"
        description="Rapports qui vous ont été affectés, en attente de votre avis."
      />

      <Card>
        <CardHeader>
          <CardTitle>Dossiers affectés</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
          {isError ? <p className="text-destructive">Impossible de charger vos dossiers.</p> : null}
          {!isLoading && !isError && dossiers?.length === 0 ? (
            <p className="text-brand-grey">Aucun dossier en attente d'avis pour l'instant.</p>
          ) : null}
          {dossiers && dossiers.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-brand-grey">
                    <th className="py-2 pr-4 font-medium">Statut</th>
                    <th className="py-2 pr-4 font-medium">Type</th>
                    <th className="py-2 pr-4 font-medium">Année</th>
                    <th className="py-2 pr-4 font-medium">Déposé le</th>
                    <th className="py-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {dossiers.map((dossier) => (
                    <tr key={dossier.id} className="border-b last:border-0">
                      <td className="py-2 pr-4">
                        <Badge variant={variantStatutRapport(dossier.status)}>
                          {libelleStatutRapport(dossier.status)}
                        </Badge>
                      </td>
                      <td className="py-2 pr-4">{dossier.type}</td>
                      <td className="py-2 pr-4">{dossier.fiscal_year ?? "—"}</td>
                      <td className="py-2 pr-4">
                        {dossier.submitted_at
                          ? new Date(dossier.submitted_at).toLocaleDateString("fr-FR")
                          : "—"}
                      </td>
                      <td className="py-2">
                        <Link
                          to={`/audit/rapports/${dossier.id}`}
                          className="text-brand-green underline underline-offset-2"
                        >
                          Examiner
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
