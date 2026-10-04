import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import type { PortefeuilleResume } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { formatPourcentage, formatScore } from "@/shared/format/etatPosition";
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
import { useCreatePortfolio, useTablePortefeuilles } from "../api";
import { type CreerPortefeuilleForm, creerPortefeuilleSchema } from "../schemas";

const etat = (p: PortefeuilleResume) => (p.archived ? "Archivé" : "Actif");

/** Mes portefeuilles (table de données, tâche 5.18) : nom, encours, positions, score agrégé et
 * couverture ; scores E/S/G, dates et accès au détail dans le tiroir. Les archivés sont masqués
 * par défaut via le filtre « État ». */
export function PortfoliosPage() {
  const [modaleOuverte, setModaleOuverte] = useState(false);
  const { data, isLoading, isError } = useTablePortefeuilles();
  const [ouvertId, setOuvertId] = useState<string | null>(null);

  const colonnes = useMemo<ColonneTable<PortefeuilleResume>[]>(
    () => [
      {
        id: "nom",
        entete: "Portefeuille",
        masquable: false,
        valeurTri: (p) => p.name,
        cellule: (p) => <span className="font-semibold text-foreground">{p.name}</span>,
      },
      {
        id: "encours",
        entete: "Encours",
        alignement: "droite",
        valeurTri: (p) => p.total_amount,
        valeurExport: (p) => p.total_amount,
        cellule: (p) => (
          <span className="font-mono tabular-nums">
            {p.total_amount.toLocaleString("fr-FR")} {p.reference_currency}
          </span>
        ),
      },
      {
        id: "positions",
        entete: "Positions",
        alignement: "droite",
        valeurTri: (p) => p.position_count,
        cellule: (p) => <span className="font-mono">{p.position_count}</span>,
      },
      {
        id: "score",
        entete: "Score ESG",
        alignement: "droite",
        valeurTri: (p) => p.aggregated_esg_score,
        cellule: (p) => (
          <span className="font-mono font-semibold">{formatScore(p.aggregated_esg_score)}</span>
        ),
      },
      {
        id: "couverture",
        entete: "Couverture",
        alignement: "droite",
        valeurTri: (p) => p.esg_coverage,
        cellule: (p) => <span className="font-mono">{formatPourcentage(p.esg_coverage)}</span>,
      },
    ],
    [],
  );
  const ouvert = data?.find((p) => p.id === ouvertId) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mes portefeuilles"
        description="Créer et suivre vos portefeuilles — score ESG agrégé et couverture calculés par le serveur."
        action={<Button onClick={() => setModaleOuverte(true)}>Créer un portefeuille</Button>}
      />

      <Dialog open={modaleOuverte} onOpenChange={setModaleOuverte}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Créer un portefeuille</DialogTitle>
          </DialogHeader>
          <FormulaireCreation onCreated={() => setModaleOuverte(false)} />
        </DialogContent>
      </Dialog>

      <DataTable
        libelle="Portefeuilles"
        lignes={data}
        colonnes={colonnes}
        cle={(p) => p.id}
        rechercheDans={(p) => p.name}
        placeholderRecherche="Nom du portefeuille…"
        filtres={[
          { id: "etat", libelle: "État", valeur: etat },
          { id: "devise", libelle: "Devise", valeur: (p) => p.reference_currency },
        ]}
        filtresInitiaux={{ etat: ["Actif"] }}
        triInitial={{ colonne: "nom", sens: "asc" }}
        surOuvrir={(p) => setOuvertId(p.id)}
        libelleLigne={(p) => p.name}
        ligneActive={ouvertId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucun portefeuille pour ce filtre."
        nomExport="portefeuilles"
        memoire="investor-portefeuilles"
      />

      <Sheet open={ouvert !== null} onOpenChange={(o) => !o && setOuvertId(null)}>
        {ouvert ? (
          <SheetContent>
            <SheetHeader>
              <SheetTitle>{ouvert.name}</SheetTitle>
              <SheetDescription>
                {ouvert.total_amount.toLocaleString("fr-FR")} {ouvert.reference_currency} ·{" "}
                {ouvert.position_count} position(s)
              </SheetDescription>
              <Badge variant={ouvert.archived ? "secondary" : "success"} className="w-fit">
                {etat(ouvert)}
              </Badge>
            </SheetHeader>
            <SheetBody>
              <SheetSection titre="ESG agrégé">
                <SheetFields
                  champs={[
                    { libelle: "Score ESG", valeur: formatScore(ouvert.aggregated_esg_score) },
                    {
                      libelle: "Environnement",
                      valeur: formatScore(ouvert.aggregated_environmental_score),
                    },
                    { libelle: "Social", valeur: formatScore(ouvert.aggregated_social_score) },
                    {
                      libelle: "Gouvernance",
                      valeur: formatScore(ouvert.aggregated_governance_score),
                    },
                    { libelle: "Couverture", valeur: formatPourcentage(ouvert.esg_coverage) },
                  ]}
                />
              </SheetSection>
              <SheetSection titre="Portefeuille">
                <SheetFields
                  champs={[
                    { libelle: "Devise de référence", valeur: ouvert.reference_currency },
                    {
                      libelle: "Créé le",
                      valeur: new Date(ouvert.created_at).toLocaleDateString("fr-FR"),
                    },
                  ]}
                />
              </SheetSection>
            </SheetBody>
            <SheetFooter>
              <Button asChild size="sm">
                <Link to={`/investor/portefeuilles/${ouvert.id}`}>Ouvrir le portefeuille</Link>
              </Button>
            </SheetFooter>
          </SheetContent>
        ) : null}
      </Sheet>
    </div>
  );
}

function FormulaireCreation({ onCreated }: { onCreated: () => void }) {
  const createPortfolio = useCreatePortfolio();
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<CreerPortefeuilleForm>({
    resolver: zodResolver(creerPortefeuilleSchema),
    defaultValues: { name: "" },
  });

  function onSubmit(values: CreerPortefeuilleForm) {
    setServerError(null);
    createPortfolio.mutate(values, {
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
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Nom du portefeuille</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" className="w-full" disabled={createPortfolio.isPending}>
          {createPortfolio.isPending ? "Création..." : "Créer"}
        </Button>
      </form>
    </Form>
  );
}
