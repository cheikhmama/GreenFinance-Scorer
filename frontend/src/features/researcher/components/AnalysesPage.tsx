import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import type { AnalysePublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleStatutAnalyse, variantStatutAnalyse } from "@/shared/format/statutAnalyse";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { type ColonneTable, DataTable } from "@/shared/ui/data-table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
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
import { useCreateAnalysis, useMyAnalyses, useMyAssignedProjects, useProjectScope } from "../api";
import { type AnalyseForm, analyseFormSchema } from "../schemas";

const dateFr = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("fr-FR") : null);

/** Mes analyses, tous projets confondus — la création se fait toujours dans le contexte d'un
 * projet affecté (voir FormulaireCreation), jamais hors sol. Table de données (tâche 5.18) :
 * commentaire de l'institution et dates dans le tiroir. */
export function AnalysesPage() {
  const { data: analyses, isLoading, isError } = useMyAnalyses();
  const { data: projets } = useMyAssignedProjects();
  const [creationOuverte, setCreationOuverte] = useState(false);
  const [ouverteId, setOuverteId] = useState<string | null>(null);
  const projetsOuverts = projets?.filter((p) => p.status === "OUVERT") ?? [];

  const colonnes = useMemo<ColonneTable<AnalysePublic>[]>(() => {
    const nomProjet = (projetId: string) => projets?.find((p) => p.id === projetId)?.name ?? "—";
    return [
      {
        id: "titre",
        entete: "Titre",
        masquable: false,
        valeurTri: (a) => a.title,
        cellule: (a) => <span className="font-semibold text-foreground">{a.title}</span>,
      },
      {
        id: "projet",
        entete: "Projet",
        valeurTri: (a) => nomProjet(a.project_id),
        cellule: (a) => <span className="text-muted-foreground">{nomProjet(a.project_id)}</span>,
      },
      {
        id: "statut",
        entete: "Statut",
        alignement: "centre",
        valeurTri: (a) => libelleStatutAnalyse(a.status),
        cellule: (a) => (
          <Badge variant={variantStatutAnalyse(a.status)}>{libelleStatutAnalyse(a.status)}</Badge>
        ),
      },
      {
        id: "version",
        entete: "Version",
        alignement: "droite",
        valeurTri: (a) => a.version,
        cellule: (a) => <span className="font-mono">{a.version}</span>,
      },
      {
        id: "cree",
        entete: "Créée le",
        alignement: "droite",
        valeurTri: (a) => a.created_at,
        cellule: (a) => <span className="font-mono">{dateFr(a.created_at)}</span>,
      },
    ];
  }, [projets]);

  const nomProjet = (projetId: string) => projets?.find((p) => p.id === projetId)?.name ?? null;
  const ouverte = analyses?.find((a) => a.id === ouverteId) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analyses"
        description="Vos analyses, brouillons, soumises et décidées par l'institution."
        action={
          projetsOuverts.length > 0 ? (
            <Button onClick={() => setCreationOuverte(true)}>Créer une analyse</Button>
          ) : undefined
        }
      />

      {projetsOuverts.length === 0 ? (
        <p className="text-muted-foreground">
          Aucun projet ouvert ne vous est encore affecté — une analyse ne peut être créée que dans
          le cadre d'un projet.
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

      <DataTable
        libelle="Mes analyses"
        lignes={analyses}
        colonnes={colonnes}
        cle={(a) => a.id}
        rechercheDans={(a) => `${a.title} ${nomProjet(a.project_id) ?? ""}`}
        placeholderRecherche="Titre, projet…"
        filtres={[
          { id: "statut", libelle: "Statut", valeur: (a) => libelleStatutAnalyse(a.status) },
          { id: "projet", libelle: "Projet", valeur: (a) => nomProjet(a.project_id) },
        ]}
        triInitial={{ colonne: "cree", sens: "desc" }}
        surOuvrir={(a) => setOuverteId(a.id)}
        libelleLigne={(a) => a.title}
        ligneActive={ouverteId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucune analyse pour l’instant."
        nomExport="mes-analyses"
        memoire="chercheur-analyses"
      />

      <Sheet open={ouverte !== null} onOpenChange={(o) => !o && setOuverteId(null)}>
        {ouverte ? (
          <SheetContent>
            <SheetHeader>
              <SheetTitle>{ouverte.title}</SheetTitle>
              <SheetDescription>
                {nomProjet(ouverte.project_id) ?? "Projet"} · version {ouverte.version}
              </SheetDescription>
              <Badge variant={variantStatutAnalyse(ouverte.status)} className="w-fit">
                {libelleStatutAnalyse(ouverte.status)}
              </Badge>
            </SheetHeader>
            <SheetBody>
              <SheetSection titre="Suivi">
                <SheetFields
                  champs={[
                    { libelle: "Créée le", valeur: dateFr(ouverte.created_at) },
                    { libelle: "Soumise le", valeur: dateFr(ouverte.submitted_at) },
                    { libelle: "Décidée le", valeur: dateFr(ouverte.decided_at) },
                    {
                      libelle: "Commentaire de l’institution",
                      valeur: ouverte.institution_comment,
                    },
                  ]}
                />
              </SheetSection>
            </SheetBody>
            <SheetFooter>
              <Button asChild size="sm">
                <Link to={`/researcher/analyses/${ouverte.id}`}>Ouvrir l’analyse</Link>
              </Button>
            </SheetFooter>
          </SheetContent>
        ) : null}
      </Sheet>
    </div>
  );
}

/** Restreint le choix aux entreprises du périmètre du projet (ProjetEntreprise) — jamais toutes
 * les entreprises publiées de la plateforme : une sélection hors périmètre serait de toute façon
 * refusée côté serveur (code entreprise_hors_perimetre), un sélecteur pré-filtré évite de le
 * découvrir tardivement via une erreur générique. */
function CompaniesPicker({
  projetId,
  selectedIds,
  onChange,
}: {
  projetId: string;
  selectedIds: string[];
  onChange: (ids: string[]) => void;
}) {
  const [recherche, setRecherche] = useState("");
  const { data: perimetre, isLoading } = useProjectScope(projetId);
  const entreprises = (perimetre ?? []).filter((entreprise) =>
    entreprise.company_name.toLowerCase().includes(recherche.toLowerCase()),
  );

  function toggle(id: string) {
    onChange(selectedIds.includes(id) ? selectedIds.filter((v) => v !== id) : [...selectedIds, id]);
  }

  if (!isLoading && (perimetre ?? []).length === 0) {
    return (
      <p className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
        Aucune entreprise n'a encore été autorisée par l'institution pour ce projet.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <Input
        placeholder="Rechercher une entreprise du périmètre..."
        value={recherche}
        onChange={(event) => setRecherche(event.target.value)}
      />
      <div className="max-h-40 space-y-1 overflow-y-auto rounded-md border p-2">
        {entreprises.map((entreprise) => (
          <label key={entreprise.company_id} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={selectedIds.includes(entreprise.company_id)}
              onChange={() => toggle(entreprise.company_id)}
            />
            {entreprise.company_name}
          </label>
        ))}
        {!isLoading && entreprises.length === 0 ? (
          <p className="text-xs text-muted-foreground">Aucun résultat.</p>
        ) : null}
      </div>
    </div>
  );
}

function FormulaireAnalyse({
  projets,
  onDone,
}: {
  projets: { id: string; name: string }[];
  onDone: () => void;
}) {
  const [projetId, setProjetId] = useState(projets[0]?.id ?? "");
  const createAnalysis = useCreateAnalysis(projetId);
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<AnalyseForm>({
    resolver: zodResolver(analyseFormSchema),
    defaultValues: { title: "", content: "", company_ids: [] },
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
          <Select
            id="projet-analyse"
            value={projetId}
            onChange={(event) => {
              // Le périmètre autorisé diffère par projet — on vide la sélection plutôt que de
              // laisser une entreprise hors périmètre s'y attarder après le changement.
              setProjetId(event.target.value);
              form.setValue("company_ids", []);
            }}
          >
            {projets.map((projet) => (
              <option key={projet.id} value={projet.id}>
                {projet.name}
              </option>
            ))}
          </Select>
        </div>

        <FormField
          control={form.control}
          name="title"
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
          name="content"
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
          name="company_ids"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Entreprises comparées</FormLabel>
              <CompaniesPicker
                projetId={projetId}
                selectedIds={field.value}
                onChange={field.onChange}
              />
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
