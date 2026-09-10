import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { libelleStatutAnalyse, variantStatutAnalyse } from "@/shared/format/statutAnalyse";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { Textarea } from "@/shared/ui/textarea";
import { useCreateAnalysis, useMyAnalyses, useMyAssignedProjects, usePublishedCompaniesForResearcher } from "../api";
import { type AnalyseForm, analyseFormSchema } from "../schemas";

/** Mes analyses, tous projets confondus — la création se fait toujours dans le contexte d'un
 * projet affecté (voir FormulaireCreation), jamais hors sol. */
export function AnalysesPage() {
  const { data: analyses, isLoading, isError } = useMyAnalyses();
  const { data: projets } = useMyAssignedProjects();
  const [creationOuverte, setCreationOuverte] = useState(false);
  const projetsOuverts = projets?.filter((p) => p.statut === "OUVERT") ?? [];
  const nomProjet = (projetId: string) => projets?.find((p) => p.id === projetId)?.nom ?? "—";

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Chercheur"
        title="Analyses"
        description="Vos analyses, brouillons, soumises et décidées par l'institution."
        action={
          projetsOuverts.length > 0 ? (
            <Button onClick={() => setCreationOuverte(true)}>Créer une analyse</Button>
          ) : undefined
        }
      />

      {projetsOuverts.length === 0 ? (
        <p className="text-brand-grey">
          Aucun projet ouvert ne vous est encore affecté — une analyse ne peut être créée que dans le
          cadre d'un projet.
        </p>
      ) : null}

      <Dialog open={creationOuverte} onOpenChange={setCreationOuverte}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Créer une analyse</DialogTitle>
          </DialogHeader>
          <FormulaireAnalyse projets={projetsOuverts} onDone={() => setCreationOuverte(false)} />
        </DialogContent>
      </Dialog>

      {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
      {isError ? <p className="text-destructive">Impossible de charger les analyses.</p> : null}
      {!isLoading && !isError && analyses?.length === 0 ? (
        <p className="text-brand-grey">Aucune analyse pour l'instant.</p>
      ) : null}

      <div className="space-y-3">
        {analyses?.map((analyse) => (
          <Link key={analyse.id} to={`/researcher/analyses/${analyse.id}`}>
            <Card className="transition hover:border-brand-green">
              <CardContent className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-medium text-brand-blue">{analyse.titre}</p>
                  <p className="text-sm text-brand-grey">
                    {nomProjet(analyse.projet_id)} — version {analyse.version}
                  </p>
                </div>
                <Badge variant={variantStatutAnalyse(analyse.statut)}>
                  {libelleStatutAnalyse(analyse.statut)}
                </Badge>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

function CompaniesPicker({
  selectedIds,
  onChange,
}: {
  selectedIds: string[];
  onChange: (ids: string[]) => void;
}) {
  const [recherche, setRecherche] = useState("");
  const { data } = usePublishedCompaniesForResearcher({ recherche });
  const entreprises = data?.pages.flatMap((page) => page.items) ?? [];

  function toggle(id: string) {
    onChange(selectedIds.includes(id) ? selectedIds.filter((v) => v !== id) : [...selectedIds, id]);
  }

  return (
    <div className="space-y-2">
      <Input
        placeholder="Rechercher une entreprise..."
        value={recherche}
        onChange={(event) => setRecherche(event.target.value)}
      />
      <div className="max-h-40 space-y-1 overflow-y-auto rounded-md border p-2">
        {entreprises.map((entreprise) => (
          <label key={entreprise.id} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={selectedIds.includes(entreprise.id)}
              onChange={() => toggle(entreprise.id)}
            />
            {entreprise.nom} — {entreprise.secteur}
          </label>
        ))}
        {entreprises.length === 0 ? <p className="text-xs text-brand-grey">Aucun résultat.</p> : null}
      </div>
    </div>
  );
}

function FormulaireAnalyse({
  projets,
  onDone,
}: {
  projets: { id: string; nom: string }[];
  onDone: () => void;
}) {
  const [projetId, setProjetId] = useState(projets[0]?.id ?? "");
  const createAnalysis = useCreateAnalysis(projetId);
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<AnalyseForm>({
    resolver: zodResolver(analyseFormSchema),
    defaultValues: { titre: "", contenu: "", entreprise_ids: [] },
  });

  function onSubmit(values: AnalyseForm) {
    setServerError(null);
    createAnalysis.mutate(values, {
      onSuccess: onDone,
      onError: (error) => {
        setServerError(error instanceof ApiError ? error.message : "Échec de la création.");
      },
    });
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {serverError ? (
          <Alert variant="destructive">
            <AlertTitle>Création impossible</AlertTitle>
            <AlertDescription>{serverError}</AlertDescription>
          </Alert>
        ) : null}

        <div className="block space-y-1 text-sm">
          <label htmlFor="projet-analyse" className="font-medium">
            Projet
          </label>
          <Select id="projet-analyse" value={projetId} onChange={(event) => setProjetId(event.target.value)}>
            {projets.map((projet) => (
              <option key={projet.id} value={projet.id}>
                {projet.nom}
              </option>
            ))}
          </Select>
        </div>

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
              <FormLabel>Contenu de l'analyse</FormLabel>
              <FormControl>
                <Textarea rows={6} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="entreprise_ids"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Entreprises comparées</FormLabel>
              <CompaniesPicker selectedIds={field.value} onChange={field.onChange} />
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit" className="w-full" disabled={createAnalysis.isPending || !projetId}>
          {createAnalysis.isPending ? "Création..." : "Créer (brouillon)"}
        </Button>
      </form>
    </Form>
  );
}
