import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { libelleStatutProjet, variantStatutProjet } from "@/shared/format/statutProjet";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { Textarea } from "@/shared/ui/textarea";
import { useCreateProject, useMyProjects } from "../api";
import { type CreerProjetForm, creerProjetSchema } from "../schemas";

export function ProjectsPage() {
  const { data: projets, isLoading, isError } = useMyProjects();
  const [modaleOuverte, setModaleOuverte] = useState(false);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Institution"
        title="Projets"
        description="Créer un projet, affecter des chercheurs, recevoir et décider de leurs analyses."
        action={<Button onClick={() => setModaleOuverte(true)}>Créer un projet</Button>}
      />

      <Dialog open={modaleOuverte} onOpenChange={setModaleOuverte}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Créer un projet</DialogTitle>
          </DialogHeader>
          <FormulaireCreation onCreated={() => setModaleOuverte(false)} />
        </DialogContent>
      </Dialog>

      {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
      {isError ? <p className="text-destructive">Impossible de charger les projets.</p> : null}
      {!isLoading && !isError && projets?.length === 0 ? (
        <p className="text-brand-grey">Aucun projet pour l'instant.</p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        {projets?.map((projet) => (
          <Link key={projet.id} to={`/institution/projets/${projet.id}`}>
            <Card className="h-full transition hover:border-brand-green">
              <CardHeader className="flex flex-row items-start justify-between gap-2">
                <CardTitle className="text-base text-brand-blue">{projet.nom}</CardTitle>
                <Badge variant={variantStatutProjet(projet.statut)}>{libelleStatutProjet(projet.statut)}</Badge>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-brand-grey">{projet.description ?? "Aucune description."}</p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

function FormulaireCreation({ onCreated }: { onCreated: () => void }) {
  const createProject = useCreateProject();
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<CreerProjetForm>({
    resolver: zodResolver(creerProjetSchema),
    defaultValues: { nom: "", description: "" },
  });

  function onSubmit(values: CreerProjetForm) {
    setServerError(null);
    createProject.mutate(values, {
      onSuccess: onCreated,
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
        <FormField
          control={form.control}
          name="nom"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Nom du projet</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description (optionnelle)</FormLabel>
              <FormControl>
                <Textarea rows={3} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" className="w-full" disabled={createProject.isPending}>
          {createProject.isPending ? "Création..." : "Créer"}
        </Button>
      </form>
    </Form>
  );
}
