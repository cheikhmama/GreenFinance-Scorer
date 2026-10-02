import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Download, FileWarning } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import type {
  RapportESGDetail,
  ScoreESGPublic,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleCauseExtraction } from "@/shared/format/causeExtraction";
import {
  formatValeur,
  libelleIndicateur,
  libelleMethode,
  libellePilier,
} from "@/shared/format/indicateurs";
import {
  libelleStatutRapportEntreprise,
  variantStatutRapportEntreprise,
} from "@/shared/format/statut";
import { titreDeclaration } from "@/shared/format/typeRapport";
import { PageShell } from "@/shared/layout/PageShell";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { FileDrop } from "@/shared/ui/file-drop";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Skeleton } from "@/shared/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { useCompanyReport, useReportChecklist, useSubmitCorrection } from "../api";
import { type CorrectionForm, correctionSchema } from "../schemas";
import { DraftPanel } from "../session/DraftPanel";
import { etatBrouillon, libelleExercice } from "../session/etat";
import { LockBanner } from "../session/LockBanner";
import { SessionStepper } from "../session/SessionStepper";
import { SubmitDialog } from "../session/SubmitDialog";

const ANNEE_COURANTE = new Date().getFullYear();
const DECISIONS = ["VALIDATED", "REJECTED", "REVISION_REQUESTED"];

function RetourListe() {
  return (
    <Button asChild variant="ghost" size="sm" className="-ml-2 text-muted-foreground">
      <Link to="/company/declarations">
        <ArrowLeft aria-hidden="true" />
        Mes déclarations
      </Link>
    </Button>
  );
}

/** Une déclaration (tâches 5.8, 5.9) : en-tête standard, étapes, puis selon l'état — préparation
 * du brouillon, bandeau de verrouillage, score officiel une fois validée, correction demandée,
 * valeurs extraites (lecture seule). */
export function CompanyReportDetailPage() {
  const { rapportId } = useParams<{ rapportId: string }>();
  const { data: rapport, isLoading, isError } = useCompanyReport(rapportId ?? "");
  const [soumissionOuverte, setSoumissionOuverte] = useState(false);
  const etat = rapport ? etatBrouillon(rapport) : null;
  const liste = useReportChecklist(
    rapportId ?? "",
    etat === "PRET" ? (rapport?.extraction_finished_at ?? null) : null,
  );

  if (isLoading) {
    return (
      <div className="space-y-6" aria-busy="true">
        <RetourListe />
        <Skeleton className="h-14 w-2/3" />
        <Skeleton className="h-8 w-full max-w-xl" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (isError || !rapport) {
    return (
      <div className="space-y-6">
        <RetourListe />
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-6 text-center">
            <FileWarning className="size-8 text-muted-foreground" aria-hidden="true" />
            <p className="font-medium text-foreground">Déclaration introuvable</p>
            <p className="text-sm text-muted-foreground">
              Elle a peut-être été abandonnée, ou le lien est incomplet.
            </p>
            <Button asChild variant="outline">
              <Link to="/company/declarations">Retour à mes déclarations</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const decidee = DECISIONS.includes(rapport.status);
  const exercice = libelleExercice(rapport.fiscal_year);

  return (
    <div className="space-y-2">
      <RetourListe />
      <PageShell
        title={titreDeclaration(rapport)}
        description={
          <>
            {exercice} · version {rapport.version}
            {rapport.previous_report_id ? " (correction)" : ""}
            {rapport.original_filename ? ` · ${rapport.original_filename}` : ""}
          </>
        }
        actions={
          <>
            <Badge variant={variantStatutRapportEntreprise(rapport.status)}>
              {libelleStatutRapportEntreprise(rapport.status)}
            </Badge>
            {rapport.synthesis_available ? (
              <Button asChild variant="outline" size="sm">
                <a href={`/api/v1/company/rapports/${rapport.id}/synthese/fichier`}>
                  <Download aria-hidden="true" />
                  Synthèse PDF
                </a>
              </Button>
            ) : null}
          </>
        }
      >
        <SessionStepper rapport={rapport} />

        {/* Cause affichée seulement tant que l'échec est l'état courant du rapport. */}
        {rapport.extraction_error && rapport.status === "EXTRACTION_FAILED" ? (
          <Alert variant="destructive">
            <AlertTitle>Échec de la lecture du fichier</AlertTitle>
            <AlertDescription>{libelleCauseExtraction(rapport.extraction_error)}</AlertDescription>
          </Alert>
        ) : null}

        {rapport.submitted_at ? (
          <LockBanner
            submittedAt={rapport.submitted_at}
            checksum={rapport.checksum_sha256}
            close={decidee}
          />
        ) : null}

        {etat ? (
          <DraftPanel
            rapport={rapport}
            etat={etat}
            groupes={liste.data}
            chargementListe={liste.isPending}
            onSoumettre={() => setSoumissionOuverte(true)}
          />
        ) : null}
        <SubmitDialog
          rapport={rapport}
          groupes={liste.data ?? []}
          open={soumissionOuverte}
          onOpenChange={setSoumissionOuverte}
        />

        {rapport.status === "VALIDATED" && rapport.official_score ? (
          <ScoreOfficiel score={rapport.official_score} />
        ) : null}

        {rapport.status === "REVISION_REQUESTED" ? (
          <FormulaireCorrection rapportId={rapport.id} exercice={rapport.fiscal_year} />
        ) : null}

        {etat ? null : <ValeursExtraites rapport={rapport} />}
      </PageShell>
    </div>
  );
}

function arrondi(valeur: number) {
  return valeur.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
}

/** Score officiel d'une déclaration validée : global, puis un score par pilier. */
function ScoreOfficiel({ score }: { score: ScoreESGPublic }) {
  const piliers = [
    ["Environnement", score.environmental_score],
    ["Social", score.social_score],
    ["Gouvernance", score.governance_score],
  ] as const;
  return (
    <Card role="region" aria-label="Score officiel">
      <CardHeader>
        <CardTitle className="text-base">Score officiel</CardTitle>
        <CardDescription>
          Calculé après validation de l’auditeur
          {score.coverage_rate != null
            ? ` · couverture ${Math.round(score.coverage_rate * 100)} %`
            : ""}{" "}
          · configuration v{score.config_version}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 sm:grid-cols-[auto_1fr] sm:items-center">
        <p className="text-4xl font-semibold tabular-nums text-foreground">
          {arrondi(score.global_score)}
          <span className="text-base font-normal text-muted-foreground">/100</span>
        </p>
        <ul className="space-y-3 sm:border-l sm:pl-6">
          {piliers.map(([libelle, valeur]) => (
            <li key={libelle} className="grid grid-cols-[7rem_1fr_3rem] items-center gap-3">
              <span className="text-sm text-muted-foreground">{libelle}</span>
              <span
                className="h-2 overflow-hidden rounded-full bg-muted"
                role="progressbar"
                aria-label={libelle}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={valeur ?? undefined}
              >
                <span
                  className="block h-full rounded-full bg-primary"
                  style={{ width: `${valeur ?? 0}%` }}
                />
              </span>
              <span className="text-right text-sm font-medium tabular-nums text-foreground">
                {valeur != null ? arrondi(valeur) : "—"}
              </span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function pages(preuve: { page_start: number; page_end: number }) {
  return preuve.page_start === preuve.page_end
    ? `p. ${preuve.page_start}`
    : `p. ${preuve.page_start}–${preuve.page_end}`;
}

/** Indicateurs et données carbone d'un rapport soumis (un brouillon n'en montre aucun, tâche
 * 5.8 : seule la liste de complétude, en comptes). */
function ValeursExtraites({ rapport }: { rapport: RapportESGDetail }) {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Indicateurs ESG</CardTitle>
          <CardDescription>
            Valeurs lues dans le rapport transmis, avec la page où elles figurent.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {rapport.declared_global_score !== null ? (
            <p className="text-sm text-muted-foreground">
              Score ESG global auto-déclaré :{" "}
              <strong className="text-foreground">
                {arrondi(rapport.declared_global_score)}/100
              </strong>
              {rapport.declared_global_score_proof
                ? ` · ${pages(rapport.declared_global_score_proof)}`
                : ""}
            </p>
          ) : null}
          {rapport.metrics.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Aucun indicateur extrait pour l’instant.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Indicateur</TableHead>
                  <TableHead>Pilier</TableHead>
                  <TableHead className="text-right">Valeur</TableHead>
                  <TableHead>Méthode</TableHead>
                  <TableHead>Source</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rapport.metrics.map((indicateur) => (
                  <TableRow key={indicateur.id}>
                    <TableCell className="font-medium text-foreground">
                      {libelleIndicateur(indicateur.metric_code)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {libellePilier(indicateur.pillar)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatValeur(indicateur.value, indicateur.unit)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {libelleMethode(indicateur.method)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {pages(indicateur.proof)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Données carbone</CardTitle>
          <CardDescription>Émissions de gaz à effet de serre par scope.</CardDescription>
        </CardHeader>
        <CardContent>
          {rapport.carbon_data.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Aucune donnée carbone extraite pour l’instant.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Scope</TableHead>
                  <TableHead className="text-right">Émissions</TableHead>
                  <TableHead>Méthode</TableHead>
                  <TableHead>Qualité PCAF</TableHead>
                  <TableHead>Source</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rapport.carbon_data.map((donnee) => (
                  <TableRow key={donnee.id}>
                    <TableCell className="font-medium text-foreground">
                      Scope {donnee.scope}
                      {donnee.ghg_category ? (
                        <span className="block text-xs font-normal text-muted-foreground">
                          {donnee.ghg_category}
                        </span>
                      ) : null}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatValeur(donnee.tonnes_co2e, "tCO2e")}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {libelleMethode(donnee.method)}
                    </TableCell>
                    <TableCell className="text-muted-foreground tabular-nums">
                      {donnee.pcaf_data_quality != null ? `${donnee.pcaf_data_quality}/5` : "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{pages(donnee.proof)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </>
  );
}

/** Correction demandée par l'auditeur : une nouvelle version, liée à celle-ci, pour le même
 * exercice par défaut (l'année courante n'est qu'un repli si l'exercice est inconnu). */
function FormulaireCorrection({
  rapportId,
  exercice,
}: {
  rapportId: string;
  exercice: number | null;
}) {
  const submitCorrection = useSubmitCorrection(rapportId);
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<CorrectionForm>({
    resolver: zodResolver(correctionSchema),
    defaultValues: { annee_reporting: exercice ?? ANNEE_COURANTE },
  });

  function onSubmit(values: CorrectionForm) {
    setServerError(null);
    submitCorrection.mutate(values, {
      onError: (error) => {
        setServerError(
          error instanceof ApiError ? error.message : "Une erreur inattendue est survenue.",
        );
      },
    });
  }

  if (submitCorrection.isSuccess) {
    return (
      <Alert role="status" className="border-primary/20 bg-secondary/60">
        <AlertTitle>Nouvelle version déposée</AlertTitle>
        <AlertDescription>
          Votre correction a été envoyée et sera traitée comme un nouveau rapport.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Card className="border-amber-300 dark:border-amber-900">
      <CardHeader>
        <CardTitle className="text-base">Correction demandée</CardTitle>
        <CardDescription>
          Déposez une nouvelle version de ce rapport. L’original reste conservé tel quel.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
            {serverError ? (
              <Alert variant="destructive">
                <AlertTitle>Dépôt impossible</AlertTitle>
                <AlertDescription>{serverError}</AlertDescription>
              </Alert>
            ) : null}
            <div className="grid grid-cols-1 items-start gap-4 sm:grid-cols-[10rem_1fr]">
              <FormField
                control={form.control}
                name="annee_reporting"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Exercice</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        className="h-11"
                        {...field}
                        onChange={(event) => field.onChange(event.target.valueAsNumber)}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="fichier"
                render={({ field: { value, onChange, onBlur, name, ref } }) => (
                  <FormItem>
                    <FormLabel>Fichier PDF corrigé</FormLabel>
                    <FormControl>
                      <FileDrop
                        accept="application/pdf"
                        hint="PDF, 50 Mo au maximum"
                        file={value}
                        onFile={onChange}
                        name={name}
                        ref={ref}
                        onBlur={onBlur}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <Button type="submit" disabled={submitCorrection.isPending}>
              {submitCorrection.isPending ? "Envoi en cours…" : "Envoyer la correction"}
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
