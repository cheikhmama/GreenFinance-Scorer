import { Link } from "react-router-dom";
import {
  libelleStatutRapportEntreprise,
  variantStatutRapportEntreprise,
} from "@/shared/format/statut";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { useCompanyReports } from "../api";

/** Liste des rapports déposés par l'entreprise connectée, chacun avec un lien vers son détail
 * (CompanyReportDetailPage.tsx) — le dépôt lui-même vit sur sa propre page (CompanyDepositPage),
 * pour ne pas mélanger consultation et action sur un même écran (voir CompanyDashboardPage). */
export function CompanyReportsPage() {
  const { data: rapports, isLoading, isError } = useCompanyReports();

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Entreprise"
        title="Mes rapports"
        description="Suivez le cycle d'extraction, d'audit et de décision de chaque rapport déposé."
        action={
          <Button asChild>
            <Link to="/company/deposer">Déposer un rapport</Link>
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Rapports déposés</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
          {isError ? <p className="text-destructive">Impossible de charger vos rapports.</p> : null}
          {!isLoading && !isError && rapports?.length === 0 ? (
            <p className="text-brand-grey">Aucun rapport déposé pour l'instant.</p>
          ) : null}
          {rapports && rapports.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-brand-grey">
                    <th className="py-2 pr-4 font-medium">Statut</th>
                    <th className="py-2 pr-4 font-medium">Type</th>
                    <th className="py-2 pr-4 font-medium">Année</th>
                    <th className="py-2 pr-4 font-medium">Déposé le</th>
                    <th className="py-2 pr-4 font-medium">Version</th>
                    <th className="py-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {rapports.map((rapport) => (
                    <tr key={rapport.id} className="border-b last:border-0">
                      <td className="py-2 pr-4">
                        <div className="flex flex-col gap-1">
                          <Badge variant={variantStatutRapportEntreprise(rapport.status)}>
                            {libelleStatutRapportEntreprise(rapport.status)}
                          </Badge>
                          {/* Message actionnable seulement tant que l'échec est l'état courant. */}
                          {rapport.extraction_error && rapport.status === "EXTRACTION_FAILED" ? (
                            <span className="text-xs text-destructive">
                              Échec d'extraction récupérable — nouvelle version possible.
                            </span>
                          ) : null}
                        </div>
                      </td>
                      <td className="py-2 pr-4">{rapport.type}</td>
                      <td className="py-2 pr-4">{rapport.fiscal_year ?? "—"}</td>
                      <td className="py-2 pr-4">
                        {rapport.submitted_at
                          ? new Date(rapport.submitted_at).toLocaleDateString("fr-FR")
                          : "Brouillon"}
                      </td>
                      <td className="py-2 pr-4">v{rapport.version}</td>
                      <td className="py-2">
                        <Link
                          to={`/company/rapports/${rapport.id}`}
                          className="text-brand-green underline underline-offset-2"
                        >
                          Voir le détail
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
