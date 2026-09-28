import { zodResolver } from "@hookform/resolvers/zod";
import { FolderKanban } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { libelleStatutProjet, variantStatutProjet } from "@/shared/format/statutProjet";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/ui/dialog";
import { EmptyState } from "@/shared/ui/empty-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { Textarea } from "@/shared/ui/textarea";
import { useCreateProject, useMyProjects } from "../api";
import { type CreerProjetForm, creerProjetSchema } from "../schemas";

function formatPeriode(projet: {
  date_debut: string | null;
  date_fin_prevue: string | null;
  date_limite: string | null;
}): string | null {
  const morceaux: string[] = [];
  if (projet.date_debut) morceaux.push(`Du ${new Date(projet.date_debut).toLocaleDateString("fr-FR")}`);
  if (projet.date_fin_prevue) morceaux.push(`au ${new Date(projet.date_fin_prevue).toLocaleDateString("fr-FR")}`);
  if (projet.date_limite) {
    morceaux.push(`échéance : ${new Date(projet.date_limite).toLocaleDateString("fr-FR")}`);
  }
  return morceaux.length > 0 ? morceaux.join(" — ") : null;
}

export function ProjectsPage() {
  const { data: projets, isLoading, isError } = useMyProjects();
  const [modaleOuverte, setModaleOuverte] = useState(false);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Institution"
        title="Projets"
        description="Créer un projet, définir son périmètre et ses documents, affecter des chercheurs, décider de leurs analyses."
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

      {isLoading ? <CardListSkeleton /> : null}
      {isError ? <p className="text-destructive">Impossible de charger les projets.</p> : null}
      {!isLoading && !isError && projets?.length === 0 ? (
        <EmptyState
          icon={FolderKanban}
          message="Aucun projet pour l'instant — créez-en un pour commencer à inviter des chercheurs et définir un périmètre d'analyse."
          action={
            <Button size="sm" onClick={() => setModaleOuverte(true)}>
              Créer un projet
            </Button>
          }
        />
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        {projets?.map((projet) => {
          const periode = formatPeriode(projet);
          return (
            <Link key={projet.id} to={`/institution/projets/${projet.id}`}>
              <Card className="h-full gap-3 transition hover:border-brand-green hover:shadow-md">
                <CardContent className="space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-base font-semibold text-brand-blue">{projet.nom}</p>
                    <Badge variant={variantStatutProjet(projet.statut)}>
                      {libelleStatutProjet(projet.statut)}
                    </Badge>
                  </div>
                  <p className="text-sm text-brand-grey">
                    {projet.objectif ?? projet.description ?? "Aucune description."}
                  </p>
                  {periode ? <p className="text-xs text-brand-grey">{periode}</p> : null}
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function FormulaireCreation({ onCreated }: { onCreated: () => void }) {
  const createProject = useCreateProject();
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<CreerProjetForm>({
    resolver: zodResolver(creerProjetSchema),
    defaultValues: {
      nom: "",
      description: "",
      objectif: "",
      date_debut: "",
      date_fin_prevue: "",
      date_limite: "",
    },
  });

  function onSubmit(values: CreerProjetForm) {
    setServerError(null);
    createProject.mutate(
      {
        nom: values.nom,
        description: values.description || null,
        objectif: values.objectif || null,
        date_debut: values.date_debut || null,
        date_fin_prevue: values.date_fin_prevue || null,
        date_limite: values.date_limite || null,
      },
      {
        onSuccess: onCreated,
        onError: (error) => {
          setServerError(error instanceof ApiError ? error.message : "Échec de la création.");
        },
      },
    );
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
          name="objectif"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Objectif (optionnel)</FormLabel>
              <FormControl>
                <Input placeholder="Ex. Analyse comparative ESG du secteur minier" {...field} />
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
        <div className="grid gap-4 sm:grid-cols-3">
          <FormField
            control={form.control}
            name="date_debut"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Début</FormLabel>
                <FormControl>
                  <Input type="date" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="date_fin_prevue"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Fin prévue</FormLabel>
                <FormControl>
                  <Input type="date" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="date_limite"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Date limite</FormLabel>
                <FormControl>
                  <Input type="date" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <Button type="submit" className="w-full" disabled={createProject.isPending}>
          {createProject.isPending ? "Création..." : "Créer"}
        </Button>
      </form>
    </Form>
  );
}
