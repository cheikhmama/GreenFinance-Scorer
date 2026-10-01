import { Download, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { RapportESGPublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  libelleStatutRapportEntreprise,
  variantStatutRapportEntreprise,
} from "@/shared/format/statut";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { Skeleton } from "@/shared/ui/skeleton";
import { useCompanyReports, useMyCompanyProfile } from "../api";
import { libelleExercice, separerDeclarations } from "../session/etat";
import { NewDeclarationDialog } from "../session/NewDeclarationDialog";
import { SessionStepper } from "../session/SessionStepper";

function StatutEntreprise({ rapport }: { rapport: RapportESGPublic }) {
  const soumis = rapport.submitted_at !== null;
  return (
    <Badge variant={variantStatutRapportEntreprise(rapport.status, soumis)}>
      {libelleStatutRapportEntreprise(rapport.status, soumis)}
    </Badge>
  );
}

function date(iso: string | null) {
  return iso ? new Date(iso).toLocaleDateString("fr-FR") : "—";
}

/** Mes déclarations (tâche 5.9) : l'action « Nouvelle déclaration » dans l'en-tête, les
 * déclarations en cours avec leur stepper, puis l'historique (score officiel, PDF de synthèse,
 * empreinte du fichier). */
export function CompanyDeclarationsPage() {
  const { data: rapports, isPending, isError } = useCompanyReports();
  const { data: entreprise } = useMyCompanyProfile();
  const [creation, setCreation] = useState(false);
  const { enCours, historique } = separerDeclarations(rapports ?? []);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={entreprise?.name}
        title="Mes déclarations"
        description="Préparez, soumettez et suivez vos déclarations ESG par exercice."
        action={
          <Button onClick={() => setCreation(true)}>
            <Plus />
            Nouvelle déclaration
          </Button>
        }
      />
      <NewDeclarationDialog open={creation} onOpenChange={setCreation} />

      {isPending ? <Skeleton className="h-40 w-full" /> : null}
      {isError ? <p className="text-destructive">Impossible de charger vos déclarations.</p> : null}

      {rapports ? (
        <section aria-labelledby="titre-en-cours" className="space-y-3">
          <h2 id="titre-en-cours" className="text-lg font-semibold text-brand-blue">
            En cours
          </h2>
          {enCours.length === 0 ? (
            <p className="rounded-lg border p-4 text-sm text-brand-grey">
              Aucune déclaration en cours. Ouvrez-en une avec « Nouvelle déclaration ».
            </p>
          ) : (
            <ul className="space-y-3">
              {enCours.map((rapport) => (
                <li key={rapport.id}>
                  <Card className="gap-3 py-4">
                    <CardContent className="space-y-3 px-5">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-brand-blue">
                            {libelleExercice(rapport.fiscal_year)}
                          </span>
                          <span className="text-sm text-brand-grey">
                            {rapport.type} · v{rapport.version}
                          </span>
                          <StatutEntreprise rapport={rapport} />
                        </div>
                        <Button asChild variant="outline" size="sm">
                          <Link to={`/company/declarations/${rapport.id}`}>Ouvrir</Link>
                        </Button>
                      </div>
                      <SessionStepper rapport={rapport} />
                    </CardContent>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {rapports ? (
        <Card>
          <CardHeader>
            <CardTitle>Historique</CardTitle>
          </CardHeader>
          <CardContent>
            {historique.length === 0 ? (
              <p className="text-sm text-brand-grey">Aucune déclaration close pour l’instant.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-brand-grey">
                      <th className="py-2 pr-4 font-medium">Exercice</th>
                      <th className="py-2 pr-4 font-medium">Statut</th>
                      <th className="py-2 pr-4 font-medium">Soumis le</th>
                      <th className="py-2 pr-4 font-medium">Score officiel</th>
                      <th className="py-2 pr-4 font-medium">SHA-256</th>
                      <th className="py-2 pr-4 font-medium">Synthèse</th>
                      <th className="py-2 font-medium" />
                    </tr>
                  </thead>
                  <tbody>
                    {historique.map((rapport) => (
                      <tr key={rapport.id} className="border-b last:border-0">
                        <td className="py-2 pr-4 font-medium text-brand-blue">
                          {libelleExercice(rapport.fiscal_year)}
                          <span className="block text-xs font-normal text-brand-grey">
                            {rapport.type} · v{rapport.version}
                          </span>
                        </td>
                        <td className="py-2 pr-4">
                          <StatutEntreprise rapport={rapport} />
                        </td>
                        <td className="py-2 pr-4">{date(rapport.submitted_at)}</td>
                        <td className="py-2 pr-4 tabular-nums">
                          {rapport.official_global_score != null ? (
                            <>
                              {rapport.official_global_score.toLocaleString("fr-FR", {
                                maximumFractionDigits: 1,
                              })}
                              /100
                              {rapport.coverage_rate != null ? (
                                <span className="block text-xs text-brand-grey">
                                  couverture {Math.round(rapport.coverage_rate * 100)} %
                                </span>
                              ) : null}
                            </>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="py-2 pr-4">
                          {rapport.checksum_sha256 ? (
                            <code className="font-mono text-xs" title={rapport.checksum_sha256}>
                              {rapport.checksum_sha256.slice(0, 12)}…
                            </code>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="py-2 pr-4">
                          {rapport.synthesis_available ? (
                            <a
                              href={`/api/v1/company/rapports/${rapport.id}/synthese/fichier`}
                              className="inline-flex items-center gap-1 text-brand-green underline underline-offset-2"
                            >
                              <Download className="size-4" aria-hidden="true" />
                              PDF
                            </a>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="py-2">
                          <Link
                            to={`/company/declarations/${rapport.id}`}
                            className="text-brand-green underline underline-offset-2"
                          >
                            Détail
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
