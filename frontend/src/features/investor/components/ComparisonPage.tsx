import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { usePublishedCompanies } from "../api";
import { MAX_SELECTION_COMPARAISON } from "../schemas";

/** Étape 1/2 : composer la sélection (2 à 4 entreprises) — recherche + filtre secteur, chips
 * retirables. Ne calcule ni n'affiche aucun résultat de comparaison ici : une page dédiée
 * (ComparisonResultsPage) s'en charge, pour ne jamais forcer un long défilement sur cette page
 * de sélection (voir "Lancer la comparaison" ci-dessous). Sélection persistée dans l'URL —
 * partageable, survit à un rafraîchissement. */
export function ComparisonPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const selection = (searchParams.get("ids") ?? "").split(",").filter(Boolean);
  const secteurFiltre = searchParams.get("secteur");
  const [recherche, setRecherche] = useState("");
  const rechercheDebattue = useDebouncedValue(recherche);

  const { data: toutesEntreprises } = usePublishedCompanies({});
  const entreprisesConnues = toutesEntreprises?.pages.flatMap((page) => page.items) ?? [];
  const secteursDisponibles = Array.from(new Set(entreprisesConnues.map((e) => e.sector))).sort();

  const { data: resultatsRecherche, isLoading: chargementRecherche } = usePublishedCompanies({
    recherche: rechercheDebattue,
    secteur: secteurFiltre ?? undefined,
  });
  const entreprisesTrouvees = resultatsRecherche?.pages.flatMap((page) => page.items) ?? [];

  function mettreAJourSelection(nouvelle: string[]) {
    const params = new URLSearchParams(searchParams);
    if (nouvelle.length > 0) params.set("ids", nouvelle.join(","));
    else params.delete("ids");
    setSearchParams(params);
  }

  function ajouter(id: string) {
    if (selection.includes(id) || selection.length >= MAX_SELECTION_COMPARAISON) return;
    mettreAJourSelection([...selection, id]);
  }

  function retirer(id: string) {
    mettreAJourSelection(selection.filter((v) => v !== id));
  }

  function changerSecteur(secteur: string) {
    const params = new URLSearchParams(searchParams);
    if (secteur) params.set("secteur", secteur);
    else params.delete("secteur");
    setSearchParams(params);
  }

  function entrepriseSelectionnee(id: string): { name: string; logo: string | null } | undefined {
    return (
      entreprisesConnues.find((e) => e.id === id) ?? entreprisesTrouvees.find((e) => e.id === id)
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Comparaison"
        description="Sélectionnez de 2 à 4 entreprises publiées, puis lancez la comparaison."
        action={
          <Button
            disabled={selection.length < 2}
            onClick={() => navigate(`/investor/comparaison/resultats?ids=${selection.join(",")}`)}
          >
            Lancer la comparaison
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">Sélection</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {selection.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {selection.map((id) => {
                const entreprise = entrepriseSelectionnee(id);
                return (
                  <Badge key={id} variant="secondary" className="gap-2 py-1.5 pr-1.5 pl-2">
                    <CompanyAvatar
                      nom={entreprise?.name ?? "…"}
                      logo={entreprise?.logo ?? null}
                      className="size-5"
                    />
                    {entreprise?.name ?? "…"}
                    <button
                      type="button"
                      onClick={() => retirer(id)}
                      aria-label={`Retirer ${entreprise?.name ?? "cette entreprise"} de la comparaison`}
                      className="rounded-full px-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                    >
                      ×
                    </button>
                  </Badge>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Aucune entreprise sélectionnée pour l'instant — ajoutez-en au moins deux ci-dessous.
            </p>
          )}

          {selection.length === 1 ? (
            <p className="text-sm text-muted-foreground">
              Ajoutez au moins une deuxième entreprise pour pouvoir lancer la comparaison.
            </p>
          ) : null}
          {selection.length >= MAX_SELECTION_COMPARAISON ? (
            <p className="text-sm text-muted-foreground">
              Maximum de {MAX_SELECTION_COMPARAISON} entreprises atteint — retirez-en une pour en
              ajouter une autre.
            </p>
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={recherche}
              onChange={(event) => setRecherche(event.target.value)}
              placeholder="Rechercher une entreprise par nom ou secteur..."
              className="max-w-sm"
            />
            <Select
              value={secteurFiltre ?? ""}
              onChange={(event) => changerSecteur(event.target.value)}
              className="w-56"
            >
              <option value="">Tous les secteurs</option>
              {secteursDisponibles.map((secteur) => (
                <option key={secteur} value={secteur}>
                  {secteur}
                </option>
              ))}
            </Select>
          </div>

          {chargementRecherche ? <CardListSkeleton count={2} /> : null}
          {!chargementRecherche && entreprisesTrouvees.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Aucune entreprise ne correspond à cette recherche.
            </p>
          ) : null}

          <div className="grid gap-2 sm:grid-cols-2">
            {entreprisesTrouvees.map((entreprise) => {
              const dejaSelectionnee = selection.includes(entreprise.id);
              return (
                <button
                  key={entreprise.id}
                  type="button"
                  disabled={
                    dejaSelectionnee ? false : selection.length >= MAX_SELECTION_COMPARAISON
                  }
                  onClick={() =>
                    dejaSelectionnee ? retirer(entreprise.id) : ajouter(entreprise.id)
                  }
                  className={`flex items-center gap-2 rounded-md border p-2 text-left text-sm transition disabled:cursor-not-allowed disabled:opacity-50 ${
                    dejaSelectionnee
                      ? "border-brand-green bg-brand-green-light/40"
                      : "border-transparent hover:border-border hover:bg-muted/50"
                  }`}
                >
                  <CompanyAvatar nom={entreprise.name} logo={entreprise.logo} className="size-8" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-foreground">
                      {entreprise.name}
                    </span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {entreprise.sector}
                    </span>
                  </span>
                  <span className="shrink-0 text-xs font-medium text-foreground">
                    {dejaSelectionnee ? "Retirer" : "Ajouter"}
                  </span>
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
