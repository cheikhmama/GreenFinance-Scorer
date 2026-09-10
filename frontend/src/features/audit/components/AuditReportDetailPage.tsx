import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Select } from "@/shared/ui/select";
import { Textarea } from "@/shared/ui/textarea";
import { useAssignedReport, useSubmitOpinion } from "../api";
import { DecisionAudit, type SoumettreAvisForm, soumettreAvisSchema } from "../schemas";

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
          {libelleStatutRapport(dossier.statut)}
        </Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Indicateurs ESG</CardTitle>
        </CardHeader>
        <CardContent>
          {dossier.indicateurs.length === 0 ? (
            <p className="text-brand-grey">Aucun indicateur extrait.</p>
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
                  {dossier.indicateurs.map((indicateur) => (
                    <tr key={indicateur.id} className="border-b last:border-0">
                      <td className="py-2 pr-4">{indicateur.pilier}</td>
                      <td className="py-2 pr-4">{indicateur.code}</td>
                      <td className="py-2 pr-4">
                        {indicateur.valeur} {indicateur.unite}
                      </td>
                      <td className="py-2 pr-4">{indicateur.methode}</td>
                      <td className="py-2 text-brand-grey">
                        {indicateur.preuve.nom_document} — p.{indicateur.preuve.page_debut}
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
          {dossier.donnees_carbone.length === 0 ? (
            <p className="text-brand-grey">Aucune donnée carbone extraite.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-brand-grey">
                    <th className="py-2 pr-4 font-medium">Scope</th>
                    <th className="py-2 pr-4 font-medium">Valeur</th>
                    <th className="py-2 pr-4 font-medium">Qualité PCAF</th>
                    <th className="py-2 font-medium">Preuve</th>
                  </tr>
                </thead>
                <tbody>
                  {dossier.donnees_carbone.map((donnee) => (
                    <tr key={donnee.id} className="border-b last:border-0">
                      <td className="py-2 pr-4">Scope {donnee.scope}</td>
                      <td className="py-2 pr-4">{donnee.valeur_tonnes_co2e} tCO2e</td>
                      <td className="py-2 pr-4">{donnee.score_qualite_pcaf}/5</td>
                      <td className="py-2 text-brand-grey">
                        {donnee.preuve.nom_document} — p.{donnee.preuve.page_debut}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {dossier.statut === "AFFECTE_AUDITEUR" ? (
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
