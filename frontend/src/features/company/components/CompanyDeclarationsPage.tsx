import { Download, Info, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { RapportESGPublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  libelleStatutRapportEntreprise,
  variantStatutRapportEntreprise,
} from "@/shared/format/statut";
import { titreDeclaration } from "@/shared/format/typeRapport";
import { PageShell } from "@/shared/layout/PageShell";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { useCompanyReports } from "../api";
import { libelleExercice, separerDeclarations } from "../session/etat";
import { NewDeclarationDialog } from "../session/NewDeclarationDialog";
import { SessionStepper } from "../session/SessionStepper";

function StatutEntreprise({ rapport }: { rapport: RapportESGPublic }) {
  return (
    <Badge variant={variantStatutRapportEntreprise(rapport.status)}>
      {libelleStatutRapportEntreprise(rapport.status)}
    </Badge>
  );
}

function date(iso: string | null) {
  return iso ? new Date(iso).toLocaleDateString("fr-FR") : "—";
}

/** Mes déclarations (tâche 5.9) : l'action « Nouvelle déclaration » dans l'en-tête, la règle
 * « une seule déclaration à la fois » en bandeau, les déclarations en cours avec leur stepper,
 * puis l'historique (score officiel, PDF de synthèse, empreinte du fichier). */
export function CompanyDeclarationsPage() {
  const { data: rapports, isPending, isError } = useCompanyReports();
  const [creation, setCreation] = useState(false);
  const { enCours, historique, sessionBloquante } = separerDeclarations(rapports ?? []);
  const exercicesValides = (rapports ?? [])
    .filter((r) => r.status === "VALIDATED" && r.fiscal_year !== null)
    .map((r) => r.fiscal_year as number);

  return (
    <PageShell
      title="Mes déclarations"
      description="Préparez, soumettez et suivez vos déclarations ESG par exercice."
      actions={
        <Button
          onClick={() => setCreation(true)}
          disabled={!rapports || sessionBloquante !== undefined}
          aria-describedby={sessionBloquante ? "raison-blocage" : undefined}
        >
          <Plus />
          Nouvelle déclaration
        </Button>
      }
    >
      {sessionBloquante ? (
        <Alert id="raison-blocage" role="note" className="bg-muted/50">
          <Info className="text-primary" aria-hidden="true" />
          <AlertDescription>
            <p>
              <span className="font-medium text-foreground">Une seule déclaration à la fois.</span>{" "}
              Terminez la déclaration {titreDeclaration(sessionBloquante)} avant d’en ouvrir une
              autre.
            </p>
          </AlertDescription>
        </Alert>
      ) : null}
      {rapports ? (
        <NewDeclarationDialog
          open={creation}
          onOpenChange={setCreation}
          exercicesExclus={exercicesValides}
        />
      ) : null}

      {isPending ? <Skeleton className="h-40 w-full" /> : null}
      {isError ? (
        <p className="text-sm text-destructive">Impossible de charger vos déclarations.</p>
      ) : null}

      {rapports ? (
        <section aria-labelledby="titre-en-cours" className="space-y-3">
          <h2 id="titre-en-cours" className="text-lg font-semibold tracking-tight text-foreground">
            En cours
          </h2>
          {enCours.length === 0 ? (
            <Card className="py-4">
              <CardContent className="px-5 text-sm text-muted-foreground">
                Aucune déclaration en cours. Ouvrez-en une avec « Nouvelle déclaration ».
              </CardContent>
            </Card>
          ) : (
            <ul className="space-y-3">
              {enCours.map((rapport) => (
                <li key={rapport.id}>
                  <Card className="gap-4 py-5">
                    <CardContent className="space-y-4 px-5">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-foreground">
                            {libelleExercice(rapport.fiscal_year)}
                          </span>
                          <span className="text-sm text-muted-foreground">
                            {titreDeclaration(rapport)}
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
            <CardTitle className="text-base">Historique</CardTitle>
          </CardHeader>
          <CardContent>
            {historique.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Aucune déclaration close pour l’instant.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead>Exercice</TableHead>
                    <TableHead>Statut</TableHead>
                    <TableHead>Soumis le</TableHead>
                    <TableHead>Score officiel</TableHead>
                    <TableHead>SHA-256</TableHead>
                    <TableHead>Synthèse</TableHead>
                    <TableHead>
                      <span className="sr-only">Actions</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {historique.map((rapport) => (
                    <TableRow key={rapport.id}>
                      <TableCell className="font-medium text-foreground">
                        {libelleExercice(rapport.fiscal_year)}
                        <span className="block text-xs font-normal text-muted-foreground">
                          {titreDeclaration(rapport)}
                        </span>
                      </TableCell>
                      <TableCell>
                        <StatutEntreprise rapport={rapport} />
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {date(rapport.submitted_at)}
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {rapport.official_global_score != null ? (
                          <>
                            {rapport.official_global_score.toLocaleString("fr-FR", {
                              maximumFractionDigits: 1,
                            })}
                            /100
                            {rapport.coverage_rate != null ? (
                              <span className="block text-xs text-muted-foreground">
                                couverture {Math.round(rapport.coverage_rate * 100)} %
                              </span>
                            ) : null}
                          </>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell>
                        {rapport.checksum_sha256 ? (
                          <code
                            className="font-mono text-xs text-muted-foreground"
                            title={rapport.checksum_sha256}
                          >
                            {rapport.checksum_sha256.slice(0, 8)}…
                            {rapport.checksum_sha256.slice(-4)}
                          </code>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell>
                        {rapport.synthesis_available ? (
                          <a
                            href={`/api/v1/company/rapports/${rapport.id}/synthese/fichier`}
                            className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
                          >
                            <Download className="size-4" aria-hidden="true" />
                            PDF
                          </a>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button asChild variant="ghost" size="sm">
                          <Link to={`/company/declarations/${rapport.id}`}>Détail</Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      ) : null}
    </PageShell>
  );
}
