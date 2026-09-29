import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import { CarbonTable, IndicatorsTable, PreuveLien } from "@/shared/esg/EvidenceTables";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Select } from "@/shared/ui/select";
import { Textarea } from "@/shared/ui/textarea";
import { useAssignedReport, useSubmitOpinion } from "../api";
import { DecisionAudit, type SoumettreAvisForm, soumettreAvisSchema } from "../schemas";

/** URL construite en dur, même patron que les CompanyDetailPage.tsx des espaces Investisseur/
 * Chercheur/Institution (voir frontend/src/shared/esg/EvidenceTables.tsx) — pas d'attente sur la
 * régénération du client Orval, la route existe déjà (app/audit/router.py::consulter_preuve_route). */
function construireUrlPreuveAudit(rapportId: string, preuveId: string): string {
  return `/api/v1/audit/rapports/${rapportId}/preuves/${preuveId}/fichier`;
}

export function AuditReportDetailPage() {
  const { rapportId } = useParams<{ rapportId: string }>();
  const { data: dossier, isLoading, isError } = useAssignedReport(rapportId ?? "");

  if (isLoading) return <div className="p-8 text-brand-grey">Chargement...</div>;
  if (isError || !dossier) {
    return (
      <div className="p-8">
        <p className="text-destructive">Dossier introuvable.</p>
        <Link to="/audit" className="text-brand-green underline underline-offset-2">
          Retour à mes dossiers
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link to="/audit" className="text-sm text-brand-green underline underline-offset-2">
          ← Mes dossiers
        </Link>
        <h1 className="mt-2 text-2xl font-semibold text-brand-blue">
          Dossier {dossier.type} — {dossier.annee_reporting ?? "année inconnue"}
        </h1>
        <Badge className="mt-2" variant={variantStatutRapport(dossier.statut)}>
          {libelleStatutRapport(dossier.statut, dossier.statut_extraction)}
        </Badge>
      </div>

      {dossier.score_global_declare !== null ? (
        <Card>
          <CardHeader>
            <CardTitle>Score ESG global auto-déclaré</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">
              <strong className="text-brand-blue">{dossier.score_global_declare}/100</strong>
              {dossier.score_global_declare_preuve ? (
                <span className="ml-2 text-brand-grey">
                  —{" "}
                  <PreuveLien
                    preuve={dossier.score_global_declare_preuve}
                    url={construireUrlPreuveAudit(dossier.id, dossier.score_global_declare_preuve.id)}
                  />
                </span>
              ) : null}
            </p>
          </CardContent>
        </Card>
      ) : null}

      <IndicatorsTable
        indicateurs={dossier.indicateurs}
        couverture={dossier.couverture}
        construireUrlPreuve={(preuveId) => construireUrlPreuveAudit(dossier.id, preuveId)}
      />

      <CarbonTable
        donneesCarbone={dossier.donnees_carbone}
        construireUrlPreuve={(preuveId) => construireUrlPreuveAudit(dossier.id, preuveId)}
      />

      {dossier.statut === "PENDING_AUDIT" ? (
        <FormulaireAvis rapportId={dossier.id} />
      ) : (
        <Alert>
          <AlertTitle>Avis déjà rendu</AlertTitle>
          <AlertDescription>
            Ce dossier n'est plus en attente d'avis — il a déjà été transmis à l'Administrateur.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}

function FormulaireAvis({ rapportId }: { rapportId: string }) {
  const submitOpinion = useSubmitOpinion(rapportId);
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<SoumettreAvisForm>({
    resolver: zodResolver(soumettreAvisSchema),
    defaultValues: { decision: DecisionAudit.RECOMMANDE_VALIDATION, commentaire: "" },
  });

  function onSubmit(values: SoumettreAvisForm) {
    setServerError(null);
    submitOpinion.mutate(
      { decision: values.decision, commentaire: values.commentaire || null },
      {
        onError: (error) => {
          setServerError(
            error instanceof ApiError ? error.message : "Une erreur inattendue est survenue.",
          );
        },
      },
    );
  }

  if (submitOpinion.isSuccess) {
    return (
      <Alert>
        <AlertTitle>Avis transmis</AlertTitle>
        <AlertDescription>
          Votre avis a été envoyé à l'Administrateur pour décision.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Rendre un avis</CardTitle>
        <CardDescription>
          Un commentaire est requis pour recommander un rejet ou demander une clarification.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
            {serverError ? (
              <Alert variant="destructive">
                <AlertTitle>Envoi impossible</AlertTitle>
                <AlertDescription>{serverError}</AlertDescription>
              </Alert>
            ) : null}

            <FormField
              control={form.control}
              name="decision"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Décision</FormLabel>
                  <FormControl>
                    <Select {...field}>
                      <option value={DecisionAudit.RECOMMANDE_VALIDATION}>
                        Recommande la validation
                      </option>
                      <option value={DecisionAudit.RECOMMANDE_REJET}>Recommande le rejet</option>
                      <option value={DecisionAudit.DEMANDE_CLARIFICATION}>
                        Demande une clarification
                      </option>
                    </Select>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="commentaire"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Commentaire</FormLabel>
                  <FormControl>
                    <Textarea {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <Button type="submit" disabled={submitOpinion.isPending}>
              {submitOpinion.isPending ? "Envoi en cours..." : "Envoyer l'avis"}
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
