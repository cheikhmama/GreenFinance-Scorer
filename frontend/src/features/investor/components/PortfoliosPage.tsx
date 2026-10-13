import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, Search, Wallet } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import type { PortefeuilleResume } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { formatPourcentage, formatScore, variantScore } from "@/shared/format/etatPosition";
import { creerSlug } from "@/shared/format/slug";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { useCreatePortfolio, useMyPortfolios } from "../api";
import { type CreerPortefeuilleForm, creerPortefeuilleSchema } from "../schemas";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR");
}

export function PortfoliosPage() {
  const [recherche, setRecherche] = useState("");
  const [archiveFiltre, setArchiveFiltre] = useState<"actifs" | "archives" | "tous">("actifs");
  const [modaleOuverte, setModaleOuverte] = useState(false);
  const rechercheDebattue = useDebouncedValue(recherche);
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useMyPortfolios({
      archive: archiveFiltre === "tous" ? undefined : archiveFiltre === "archives",
      recherche: rechercheDebattue,
    });

  const portefeuilles = data?.pages.flatMap((page) => page.items) ?? [];

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

      <div className="flex flex-wrap items-center gap-2">
        <Select
          value={archiveFiltre}
          onChange={(event) => setArchiveFiltre(event.target.value as typeof archiveFiltre)}
          className="w-40"
        >
          <option value="actifs">Actifs</option>
          <option value="archives">Archivés</option>
          <option value="tous">Tous</option>
        </Select>
        <label htmlFor="portefeuilles-recherche" className="relative min-w-56 flex-1">
          <span className="sr-only">Rechercher un portefeuille</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            id="portefeuilles-recherche"
            value={recherche}
            onChange={(event) => setRecherche(event.target.value)}
            placeholder="Rechercher par nom"
            className="pl-9"
          />
        </label>
      </div>

      {isLoading ? <CardListSkeleton count={2} /> : null}
      {isError ? (
        <p className="text-destructive">Impossible de charger les portefeuilles.</p>
      ) : null}
      {!isLoading && !isError && portefeuilles.length === 0 ? (
        <p className="text-muted-foreground">Aucun portefeuille pour ce filtre.</p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        {portefeuilles.map((portefeuille) => (
          <PortfolioCard key={portefeuille.id} portefeuille={portefeuille} />
        ))}
      </div>

      {portefeuilles.length > 0 && hasNextPage ? (
        <Button
          variant="outline"
          size="sm"
          disabled={isFetchingNextPage}
          onClick={() => fetchNextPage()}
        >
          {isFetchingNextPage ? "Chargement..." : "Voir plus"}
        </Button>
      ) : null}
    </div>
  );
}

const TEINTE_PILIER: Record<"E" | "S" | "G", string> = {
  E: "bg-emerald-500",
  S: "bg-blue-500",
  G: "bg-violet-500",
};

/** Niveau 0-100 d'un pilier, même langage visuel que shared/esg/EsgSummary.tsx (couleurs et
 * forme de barre identiques) pour que le portefeuille se lise avec les mêmes repères qu'une
 * fiche entreprise. */
function MiniPilier({ label, valeur }: { label: "E" | "S" | "G"; valeur: number | null }) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
        <span className="text-xs font-semibold tabular-nums text-foreground">
          {formatScore(valeur)}
        </span>
      </div>
      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        {valeur !== null ? (
          <div
            className={`h-full rounded-full ${TEINTE_PILIER[label]}`}
            style={{ width: `${Math.max(0, Math.min(100, valeur))}%` }}
          />
        ) : null}
      </div>
    </div>
  );
}

/** Carte d'un portefeuille (tâche post-création) : un portefeuille tout juste créé n'a encore
 * aucune position — plutôt qu'un score à zéro et une couverture à 0 % (bruyant, trompeur), un
 * état « vide » dédié invite à la première action. Une fois alimenté, la carte structure
 * l'information par priorité de lecture : valeur totale (le chiffre qu'un investisseur cherche
 * en premier), score global, puis décomposition E/S/G — même palette que la fiche entreprise
 * (shared/esg/EsgSummary.tsx) pour une identité visuelle cohérente entre les espaces. */
function PortfolioCard({ portefeuille }: { portefeuille: PortefeuilleResume }) {
  const vide = portefeuille.position_count === 0;

  return (
    <Link
      to={`/investor/portefeuilles/${creerSlug(portefeuille.name, portefeuille.id)}`}
      className="group block h-full"
    >
      <Card className="h-full overflow-hidden transition-all duration-200 ease-out group-hover:-translate-y-0.5 group-hover:border-brand-green/70 group-hover:shadow-md">
        <CardContent className="flex h-full flex-col gap-4">
          <div className="flex items-start justify-between gap-2">
            <div className="flex min-w-0 items-start gap-3">
              <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-brand-green-light text-brand-green">
                <Wallet className="size-5" />
              </span>
              <div className="min-w-0">
                <p className="truncate font-semibold text-foreground">{portefeuille.name}</p>
                <p className="text-xs text-muted-foreground">
                  Créé le {formatDate(portefeuille.created_at)}
                </p>
              </div>
            </div>
            {portefeuille.archived ? <Badge variant="secondary">Archivé</Badge> : null}
          </div>

          {vide ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-1 rounded-lg border border-dashed py-6 text-center">
              <p className="text-sm font-medium text-foreground">Portefeuille vide</p>
              <p className="max-w-56 text-xs text-muted-foreground">
                Ajoutez une première position pour démarrer le suivi ESG et carbone.
              </p>
            </div>
          ) : (
            <>
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Valeur totale
                </p>
                <p className="mt-0.5 text-2xl font-semibold tabular-nums text-brand-blue">
                  {portefeuille.total_amount.toLocaleString("fr-FR")}{" "}
                  <span className="text-base font-medium text-muted-foreground">
                    {portefeuille.reference_currency}
                  </span>
                </p>
              </div>

              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">
                  {portefeuille.position_count} position
                  {portefeuille.position_count > 1 ? "s" : ""} · couverture{" "}
                  {formatPourcentage(portefeuille.esg_coverage)}
                </span>
                <Badge variant={variantScore(portefeuille.aggregated_esg_score)}>
                  Score {formatScore(portefeuille.aggregated_esg_score)}
                </Badge>
              </div>

              <div className="grid grid-cols-3 gap-3 border-t pt-3">
                <MiniPilier label="E" valeur={portefeuille.aggregated_environmental_score} />
                <MiniPilier label="S" valeur={portefeuille.aggregated_social_score} />
                <MiniPilier label="G" valeur={portefeuille.aggregated_governance_score} />
              </div>
            </>
          )}

          <div className="mt-auto flex items-center gap-1 pt-1 text-sm font-medium text-brand-green">
            Voir le détail
            <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" />
          </div>
        </CardContent>
      </Card>
    </Link>
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
