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
import { Input } from "@/shared/ui/input";
import { useCompanyReport, useSubmitCorrection } from "../api";
import { type CorrectionForm, correctionSchema } from "../schemas";

const ANNEE_COURANTE = new Date().getFullYear();

export function CompanyReportDetailPage() {
  const { rapportId } = useParams<{ rapportId: string }>();
  const { data: rapport, isLoading, isError } = useCompanyReport(rapportId ?? "");

  if (isLoading) return <div className="p-8 text-brand-grey">Chargement...</div>;
  if (isError || !rapport) {
    return (
      <div className="p-8">
        <p className="text-destructive">Rapport introuvable.</p>
        <Link to="/company" className="text-brand-green underline underline-offset-2">
          Retour à la liste
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link to="/company" className="text-sm text-brand-green underline underline-offset-2">
          ← Mes rapports
        </Link>
        <h1 className="mt-2 text-2xl font-semibold text-brand-blue">
          Rapport {rapport.type} — {rapport.annee_reporting ?? "année inconnue"}
        </h1>
        <div className="mt-2 flex items-center gap-2">
          <Badge variant={variantStatutRapport(rapport.statut)}>
            {libelleStatutRapport(rapport.statut)}
          </Badge>
          <span className="text-sm text-brand-grey">
            version {rapport.version}
            {rapport.rapport_precedent_id ? " (correction)" : ""}
          </span>
        </div>
        {rapport.extraction_erreur ? (
          <p className="mt-2 text-sm text-destructive">
            Échec d'extraction : {rapport.extraction_erreur}
          </p>
        ) : null}
      </div>

      {rapport.statut === "DEMANDE_CORRECTION" ? (
        <FormulaireCorrection rapportId={rapport.id} />
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Indicateurs ESG</CardTitle>
        </CardHeader>
        <CardContent>
          {rapport.indicateurs.length === 0 ? (
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
                  {rapport.indicateurs.map((indicateur) => (
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
          {rapport.donnees_carbone.length === 0 ? (
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
                  {rapport.donnees_carbone.map((donnee) => (
                    <tr key={donnee.id} className="border-b last:border-0">
                      <td className="py-2 pr-4">
                        Scope {donnee.scope}
                        {donnee.categorie_ges ? ` — ${donnee.categorie_ges}` : ""}
                      </td>
                      <td className="py-2 pr-4">{donnee.valeur_tonnes_co2e} tCO2e</td>
                      <td className="py-2 pr-4">{donnee.methode}</td>
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
    </div>
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
