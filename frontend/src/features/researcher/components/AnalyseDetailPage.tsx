import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { libelleStatutAnalyse, variantStatutAnalyse } from "@/shared/format/statutAnalyse";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { Textarea } from "@/shared/ui/textarea";
import {
  useAnalysisDetail,
  useAnalysisHistory,
  useCorrectAnalysis,
  useSubmitAnalysis,
  useUpdateAnalysis,
} from "../api";
import { type AnalyseForm, analyseFormSchema } from "../schemas";

export function AnalyseDetailPage() {
  const { analyseId = "" } = useParams();
  const { data: analyse, isLoading, isError } = useAnalysisDetail(analyseId);
  const soumettre = useSubmitAnalysis(analyseId);
  const [erreur, setErreur] = useState<string | null>(null);

  if (isLoading) return <p className="text-brand-grey">Chargement...</p>;
  if (isError || !analyse) return <p className="text-destructive">Analyse introuvable.</p>;

  const modifiable = analyse.statut === "BROUILLON";
  const corrigible = analyse.statut === "CORRECTION_DEMANDEE";

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={`Version ${analyse.version}`}
        title={analyse.titre}
        description="Analyse comparative sur des entreprises publiées."
        action={<Badge variant={variantStatutAnalyse(analyse.statut)}>{libelleStatutAnalyse(analyse.statut)}</Badge>}
      />

      <HistoriqueVersions analyseId={analyse.id} versionActuelle={analyse.version} />

      {analyse.commentaire_institution ? (
        <Alert>
          <AlertTitle>Commentaire de l'institution</AlertTitle>
          <AlertDescription>{analyse.commentaire_institution}</AlertDescription>
        </Alert>
      ) : null}
      {erreur ? <p className="text-sm text-destructive">{erreur}</p> : null}

      {modifiable || corrigible ? (
        <FormulaireAnalyse analyse={analyse} mode={corrigible ? "corriger" : "modifier"} />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base text-brand-blue">Contenu</CardTitle>
          </CardHeader>
          <CardContent className="whitespace-pre-wrap text-sm text-brand-grey">
            {analyse.contenu}
          </CardContent>
        </Card>
      )}

      {modifiable ? (
        <Button
          disabled={soumettre.isPending}
          onClick={() =>
            soumettre.mutate(undefined, {
              onError: (error) =>
                setErreur(error instanceof ApiError ? error.message : "Échec de la soumission."),
            })
          }
        >
          {soumettre.isPending ? "Soumission..." : "Soumettre à l'institution"}
        </Button>
      ) : null}
    </div>
  );
}

/** Reconstruit la chaîne complète v1 -> correction -> v2 -> ... -> validation finale (voir
 * app/researcher/analyses.py::lister_versions) — n'affiche rien si l'analyse n'a qu'une seule
 * version, l'historique n'apportant alors aucune information. */
function HistoriqueVersions({
  analyseId,
  versionActuelle,
}: {
  analyseId: string;
  versionActuelle: number;
}) {
  const { data: versions } = useAnalysisHistory(analyseId);

  if (!versions || versions.length <= 1) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base text-brand-blue">Historique des versions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {versions.map((version) => (
          <div
            key={version.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-2 text-sm"
          >
            <div className="flex items-center gap-2">
              <span className={version.version === versionActuelle ? "font-semibold text-brand-blue" : "text-brand-grey"}>
                Version {version.version}
              </span>
              {version.version === versionActuelle ? (
                <span className="text-xs text-brand-grey">(consultée)</span>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={variantStatutAnalyse(version.statut)}>
                {libelleStatutAnalyse(version.statut)}
              </Badge>
              {version.id !== analyseId ? (
                <Link
                  to={`/researcher/analyses/${version.id}`}
                  className="text-brand-green underline-offset-2 hover:underline"
                >
                  Consulter
                </Link>
              ) : null}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function FormulaireAnalyse({
  analyse,
  mode,
}: {
  analyse: { id: string; titre: string; contenu: string; entreprise_ids: string[] };
  mode: "modifier" | "corriger";
}) {
  const update = useUpdateAnalysis(analyse.id);
  const correct = useCorrectAnalysis(analyse.id);
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<AnalyseForm>({
    resolver: zodResolver(analyseFormSchema),
    defaultValues: {
      titre: analyse.titre,
      contenu: analyse.contenu,
      entreprise_ids: analyse.entreprise_ids,
    },
  });

  function onSubmit(values: AnalyseForm) {
    setServerError(null);
    const onError = (error: unknown) =>
      setServerError(error instanceof ApiError ? error.message : "Échec de l'enregistrement.");
    if (mode === "corriger") {
      correct.mutate(values, { onError });
    } else {
      update.mutate(values, { onError });
    }
  }

  const enCours = update.isPending || correct.isPending;

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {serverError ? (
          <Alert variant="destructive">
            <AlertTitle>Échec</AlertTitle>
            <AlertDescription>{serverError}</AlertDescription>
          </Alert>
        ) : null}
        <FormField
          control={form.control}
          name="titre"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Titre</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="contenu"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Contenu</FormLabel>
              <FormControl>
                <Textarea rows={8} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" disabled={enCours}>
          {enCours
            ? "Enregistrement..."
            : mode === "corriger"
              ? "Enregistrer la correction (nouvelle version)"
              : "Enregistrer le brouillon"}
        </Button>
      </form>
    </Form>
  );
}
