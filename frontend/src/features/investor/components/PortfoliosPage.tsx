import { zodResolver } from "@hookform/resolvers/zod";
import { Search } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { formatPourcentage, formatScore } from "@/shared/format/etatPosition";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { useCreatePortfolio, useMyPortfolios } from "../api";
import { type CreerPortefeuilleForm, creerPortefeuilleSchema } from "../schemas";

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
        eyebrow="Investisseur"
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
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-brand-grey" />
          <Input
            id="portefeuilles-recherche"
            value={recherche}
            onChange={(event) => setRecherche(event.target.value)}
            placeholder="Rechercher par nom"
            className="pl-9"
          />
        </label>
      </div>

      {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
      {isError ? (
        <p className="text-destructive">Impossible de charger les portefeuilles.</p>
      ) : null}
      {!isLoading && !isError && portefeuilles.length === 0 ? (
        <p className="text-brand-grey">Aucun portefeuille pour ce filtre.</p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        {portefeuilles.map((portefeuille) => (
          <Link key={portefeuille.id} to={`/investor/portefeuilles/${portefeuille.id}`}>
            <Card className="h-full transition hover:border-brand-green">
              <CardHeader className="flex flex-row items-start justify-between gap-2">
                <CardTitle className="text-base text-brand-blue">{portefeuille.name}</CardTitle>
                {portefeuille.archived ? <Badge variant="secondary">archivé</Badge> : null}
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="text-2xl font-semibold tabular-nums text-brand-blue">
                  {portefeuille.total_amount.toLocaleString("fr-FR")}{" "}
                  {portefeuille.reference_currency}
                </p>
                <p className="text-brand-grey">{portefeuille.position_count} position(s)</p>
                <div className="flex items-center gap-4 pt-1">
                  <span>
                    Score : <strong>{formatScore(portefeuille.aggregated_esg_score)}</strong>
                  </span>
                  <span>
                    Couverture : <strong>{formatPourcentage(portefeuille.esg_coverage)}</strong>
                  </span>
                </div>
              </CardContent>
            </Card>
          </Link>
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
