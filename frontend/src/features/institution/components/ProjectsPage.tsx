import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import type { ProjetPublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleStatutProjet, variantStatutProjet } from "@/shared/format/statutProjet";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { type ColonneTable, DataTable } from "@/shared/ui/data-table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFields,
  SheetFooter,
  SheetHeader,
  SheetSection,
  SheetTitle,
} from "@/shared/ui/sheet";
import { Textarea } from "@/shared/ui/textarea";
import { useCreateProject, useMyProjects } from "../api";
import { type CreerProjetForm, creerProjetSchema } from "../schemas";

const dateFr = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("fr-FR") : null);

/** Projets de l'Institution (table de données, tâche 5.18) : nom, statut et calendrier ;
 * description et dates détaillées dans le tiroir, création dans une modale. */
export function ProjectsPage() {
  const { data: projets, isLoading, isError } = useMyProjects();
  const [modaleOuverte, setModaleOuverte] = useState(false);
  const [ouvertId, setOuvertId] = useState<string | null>(null);
  const ouvert = projets?.find((p) => p.id === ouvertId) ?? null;

  const colonnes = useMemo<ColonneTable<ProjetPublic>[]>(
    () => [
      {
        id: "nom",
        entete: "Projet",
        masquable: false,
        valeurTri: (p) => p.name,
        cellule: (p) => <span className="font-semibold text-foreground">{p.name}</span>,
      },
      {
        id: "statut",
        entete: "Statut",
        alignement: "centre",
        valeurTri: (p) => libelleStatutProjet(p.status),
        cellule: (p) => (
          <Badge variant={variantStatutProjet(p.status)}>{libelleStatutProjet(p.status)}</Badge>
        ),
      },
      {
        id: "debut",
        entete: "Début",
        alignement: "droite",
        valeurTri: (p) => p.start_date,
        cellule: (p) => <span className="font-mono">{dateFr(p.start_date) ?? "—"}</span>,
      },
      {
        id: "echeance",
        entete: "Date limite",
        alignement: "droite",
        valeurTri: (p) => p.deadline ?? p.planned_end_date,
        cellule: (p) => (
          <span className="font-mono">{dateFr(p.deadline ?? p.planned_end_date) ?? "—"}</span>
        ),
      },
      {
        id: "cree",
        entete: "Créé le",
        alignement: "droite",
        valeurTri: (p) => p.created_at,
        cellule: (p) => <span className="font-mono">{dateFr(p.created_at)}</span>,
      },
    ],
    [],
  );

  return (
    <div className="space-y-6">
      <PageHeader
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

      <DataTable
        libelle="Projets"
        lignes={projets}
        colonnes={colonnes}
        cle={(p) => p.id}
        rechercheDans={(p) => `${p.name} ${p.objective ?? ""} ${p.description ?? ""}`}
        placeholderRecherche="Nom, objectif…"
        filtres={[
          { id: "statut", libelle: "Statut", valeur: (p) => libelleStatutProjet(p.status) },
        ]}
        triInitial={{ colonne: "cree", sens: "desc" }}
        surOuvrir={(p) => setOuvertId(p.id)}
        libelleLigne={(p) => p.name}
        ligneActive={ouvertId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucun projet pour l'instant — créez-en un pour commencer à inviter des chercheurs et définir un périmètre d'analyse."
        nomExport="projets"
        memoire="institution-projets"
      />
      <Sheet open={ouvert !== null} onOpenChange={(o) => !o && setOuvertId(null)}>
        {ouvert ? (
          <SheetContent>
            <SheetHeader>
              <SheetTitle>{ouvert.name}</SheetTitle>
              <SheetDescription>{ouvert.objective ?? "Aucun objectif renseigné."}</SheetDescription>
              <Badge variant={variantStatutProjet(ouvert.status)} className="w-fit">
                {libelleStatutProjet(ouvert.status)}
              </Badge>
            </SheetHeader>
            <SheetBody>
              <SheetSection titre="Calendrier">
                <SheetFields
                  champs={[
                    { libelle: "Début", valeur: dateFr(ouvert.start_date) },
                    { libelle: "Fin prévue", valeur: dateFr(ouvert.planned_end_date) },
                    { libelle: "Date limite", valeur: dateFr(ouvert.deadline) },
                    { libelle: "Créé le", valeur: dateFr(ouvert.created_at) },
                    { libelle: "Clôturé le", valeur: dateFr(ouvert.closed_at) },
                  ]}
                />
              </SheetSection>
              {ouvert.description ? (
                <SheetSection titre="Description">
                  <p className="text-sm text-foreground">{ouvert.description}</p>
                </SheetSection>
              ) : null}
            </SheetBody>
            <SheetFooter>
              <Button asChild size="sm">
                <Link to={`/institution/projets/${ouvert.id}`}>Ouvrir le projet</Link>
              </Button>
            </SheetFooter>
          </SheetContent>
        ) : null}
      </Sheet>
    </div>
  );
}

function FormulaireCreation({ onCreated }: { onCreated: () => void }) {
  const createProject = useCreateProject();
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<CreerProjetForm>({
    resolver: zodResolver(creerProjetSchema),
    defaultValues: {
      name: "",
      description: "",
      objective: "",
      start_date: "",
      planned_end_date: "",
      deadline: "",
    },
  });

  function onSubmit(values: CreerProjetForm) {
    setServerError(null);
    createProject.mutate(
      {
        name: values.name,
        description: values.description || null,
        objective: values.objective || null,
        start_date: values.start_date || null,
        planned_end_date: values.planned_end_date || null,
        deadline: values.deadline || null,
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
          name="name"
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
          name="objective"
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
            name="start_date"
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
            name="planned_end_date"
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
            name="deadline"
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
