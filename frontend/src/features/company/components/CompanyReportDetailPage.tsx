import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import type { RapportESGDetail } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleCauseExtraction } from "@/shared/format/causeExtraction";
import {
  classeStatutRapportEntreprise,
  libelleStatutRapportEntreprise,
  variantStatutRapportEntreprise,
} from "@/shared/format/statut";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { useCompanyReport, useReportChecklist, useSubmitCorrection } from "../api";
import { type CorrectionForm, correctionSchema } from "../schemas";
import { DraftPanel } from "../session/DraftPanel";
import { etatBrouillon } from "../session/etat";
import { LockBanner } from "../session/LockBanner";
import { SessionStepper } from "../session/SessionStepper";
import { SubmitDialog } from "../session/SubmitDialog";

const ANNEE_COURANTE = new Date().getFullYear();

export function CompanyReportDetailPage() {
  const { rapportId } = useParams<{ rapportId: string }>();
  const { data: rapport, isLoading, isError } = useCompanyReport(rapportId ?? "");
  const [soumissionOuverte, setSoumissionOuverte] = useState(false);
  const etat = rapport ? etatBrouillon(rapport) : null;
  const liste = useReportChecklist(
    rapportId ?? "",
    etat === "PRET" ? (rapport?.extraction_finished_at ?? null) : null,
  );

  if (isLoading) return <div className="p-8 text-brand-grey">Chargement...</div>;
  if (isError || !rapport) {
    return (
      <div className="p-8">
        <p className="text-destructive">Rapport introuvable.</p>
        <Link to="/company/declarations" className="text-brand-green underline underline-offset-2">
          Retour à la liste
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/company/declarations"
          className="text-sm text-brand-green underline underline-offset-2"
        >
          ← Mes déclarations
        </Link>
        <h1 className="mt-2 text-2xl font-semibold text-brand-blue">
          Rapport {rapport.type} — {rapport.fiscal_year ?? "année inconnue"}
        </h1>
        <div className="mt-2 flex items-center gap-2">
          <Badge
            variant={variantStatutRapportEntreprise(rapport.status)}
            className={classeStatutRapportEntreprise(rapport.status)}
          >
            {libelleStatutRapportEntreprise(rapport.status)}
          </Badge>
          <span className="text-sm text-brand-grey">
            version {rapport.version}
            {rapport.previous_report_id ? " (correction)" : ""}
          </span>
        </div>
        {/* Cause affichée seulement tant que l'échec est l'état courant du rapport. */}
        {rapport.extraction_error && rapport.status === "EXTRACTION_FAILED" ? (
          <p className="mt-2 text-sm text-destructive">
            Échec d'extraction : {libelleCauseExtraction(rapport.extraction_error)}
          </p>
        ) : null}
      </div>

      <SessionStepper rapport={rapport} />

      {rapport.submitted_at ? (
        <LockBanner submittedAt={rapport.submitted_at} checksum={rapport.checksum_sha256} />
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

      {rapport.status === "REVISION_REQUESTED" ? (
        <FormulaireCorrection rapportId={rapport.id} />
      ) : null}

      {etat ? null : <ValeursExtraites rapport={rapport} />}
    </div>
  );
}

/** Indicateurs et données carbone d'un rapport soumis (un brouillon n'en montre aucun, tâche
 * 5.8 : seule la liste de complétude, en comptes). */
function ValeursExtraites({ rapport }: { rapport: RapportESGDetail }) {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Indicateurs ESG</CardTitle>
        </CardHeader>
        <CardContent>
          {rapport.declared_global_score !== null ? (
            <p className="mb-3 text-sm">
              Score ESG global auto-déclaré par l'entreprise :{" "}
              <strong className="text-brand-blue">{rapport.declared_global_score}/100</strong>
              {rapport.declared_global_score_proof ? (
                <span className="text-brand-grey">
                  {" "}
                  — {rapport.declared_global_score_proof.document_name} — p.
                  {rapport.declared_global_score_proof.page_start}
                </span>
              ) : null}
            </p>
          ) : null}
          {rapport.metrics.length === 0 ? (
            <p className="text-brand-grey">Aucun indicateur extrait pour l'instant.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-brand-grey">
                    <th className="py-2 pr-4 font-medium">Pilier</th>
                    <th className="py-2 pr-4 font-medium">Code</th>
                    <th className="py-2 pr-4 font-medium">Valeur</th>
                    <th className="py-2 pr-4 font-medium">Méthode</th>
                    <th className="py-2 font-medium">Preuve</th>
                  </tr>
                </thead>
                <tbody>
                  {rapport.metrics.map((indicateur) => (
                    <tr key={indicateur.id} className="border-b last:border-0">
                      <td className="py-2 pr-4">{indicateur.pillar}</td>
                      <td className="py-2 pr-4">{indicateur.metric_code}</td>
                      <td className="py-2 pr-4">
                        {indicateur.value} {indicateur.unit}
                      </td>
                      <td className="py-2 pr-4">{indicateur.method}</td>
                      <td className="py-2 text-brand-grey">
                        {indicateur.proof.document_name} — p.{indicateur.proof.page_start}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Données carbone</CardTitle>
        </CardHeader>
        <CardContent>
          {rapport.carbon_data.length === 0 ? (
            <p className="text-brand-grey">Aucune donnée carbone extraite pour l'instant.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-brand-grey">
                    <th className="py-2 pr-4 font-medium">Scope</th>
                    <th className="py-2 pr-4 font-medium">Valeur</th>
                    <th className="py-2 pr-4 font-medium">Méthode</th>
                    <th className="py-2 pr-4 font-medium">Qualité PCAF</th>
                    <th className="py-2 font-medium">Preuve</th>
                  </tr>
                </thead>
                <tbody>
                  {rapport.carbon_data.map((donnee) => (
                    <tr key={donnee.id} className="border-b last:border-0">
                      <td className="py-2 pr-4">
                        Scope {donnee.scope}
                        {donnee.ghg_category ? ` — ${donnee.ghg_category}` : ""}
                      </td>
                      <td className="py-2 pr-4">{donnee.tonnes_co2e} tCO2e</td>
                      <td className="py-2 pr-4">{donnee.method}</td>
                      <td className="py-2 pr-4">
                        {donnee.pcaf_data_quality != null ? `${donnee.pcaf_data_quality}/5` : "—"}
                      </td>
                      <td className="py-2 text-brand-grey">
                        {donnee.proof.document_name} — p.{donnee.proof.page_start}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}

function FormulaireCorrection({ rapportId }: { rapportId: string }) {
  const submitCorrection = useSubmitCorrection(rapportId);
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<CorrectionForm>({
    resolver: zodResolver(correctionSchema),
    defaultValues: { annee_reporting: ANNEE_COURANTE },
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
      <Alert>
        <AlertTitle>Nouvelle version déposée</AlertTitle>
        <AlertDescription>
          Votre correction a été envoyée et sera traitée comme un nouveau rapport.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Correction demandée</CardTitle>
        <CardDescription>
          Déposez une nouvelle version de ce rapport. L'original reste conservé tel quel.
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
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="annee_reporting"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Année</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
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
                render={({ field: { onChange, onBlur, name, ref } }) => (
                  <FormItem>
                    <FormLabel>Fichier PDF corrigé</FormLabel>
                    <FormControl>
                      <Input
                        type="file"
                        accept="application/pdf"
                        name={name}
                        ref={ref}
                        onBlur={onBlur}
                        onChange={(event) => onChange(event.target.files?.[0])}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <Button type="submit" disabled={submitCorrection.isPending}>
              {submitCorrection.isPending ? "Envoi en cours..." : "Envoyer la correction"}
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
