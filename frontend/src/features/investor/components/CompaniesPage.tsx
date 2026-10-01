import { Calendar, Globe, MapPin, Search, X } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { usePublishedCompanies } from "../api";

/** Liste des entreprises publiées, présentées en cards volontairement sobres (logo, nom,
 * secteur, pays, quelques informations générales) — jamais le score ESG, les scores E/S/G ni le
 * montant minimum d'investissement ici : ces données détaillées restent réservées à la fiche
 * dédiée (voir CompanyDetailPage.tsx), accessible en cliquant sur la card. Le filtre secteur vit
 * dans l'URL (?secteur=...) pour rester partageable en lien direct, entre autres depuis le
 * Dashboard (voir InvestorDashboardPage.tsx::RepartitionSecteurCard). */
export function CompaniesPage() {
  const [recherche, setRecherche] = useState("");
  const rechercheDebattue = useDebouncedValue(recherche);
  const [searchParams, setSearchParams] = useSearchParams();
  const secteur = searchParams.get("secteur");
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    usePublishedCompanies({ recherche: rechercheDebattue, secteur: secteur ?? undefined });

  const entreprises = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Investisseur"
        title="Entreprises"
        description="Parcourez les entreprises dont les données ont été validées et publiées. Cliquez sur une entreprise pour consulter sa fiche ESG complète."
      />

      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="entreprises-recherche" className="relative block max-w-sm flex-1">
          <span className="sr-only">Rechercher une entreprise</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-brand-grey" />
          <Input
            id="entreprises-recherche"
            value={recherche}
            onChange={(event) => setRecherche(event.target.value)}
            placeholder="Rechercher par nom ou secteur"
            className="pl-9"
          />
        </label>
        {secteur ? (
          <Badge variant="secondary" className="gap-1 py-1">
            Secteur : {secteur}
            <button
              type="button"
              onClick={() => setSearchParams({})}
              aria-label="Retirer le filtre secteur"
            >
              <X className="size-3" />
            </button>
          </Badge>
        ) : null}
      </div>

      {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
      {isError ? <p className="text-destructive">Impossible de charger les entreprises.</p> : null}
      {!isLoading && !isError && entreprises.length === 0 ? (
        <p className="text-brand-grey">Aucune entreprise publiée pour l'instant.</p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {entreprises.map((entreprise) => (
          <Link
            key={entreprise.id}
            to={`/investor/entreprises/${entreprise.id}`}
            className="group block"
          >
            <Card className="h-full transition group-hover:border-brand-green group-hover:shadow-md">
              <CardContent className="flex h-full flex-col gap-3">
                <div className="flex items-start gap-3">
                  <CompanyAvatar
                    nom={entreprise.name}
                    logo={entreprise.logo}
                    className="size-14 shrink-0"
                  />
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-brand-blue">{entreprise.name}</p>
                    <Badge variant="secondary" className="mt-1">
                      {entreprise.sector}
                    </Badge>
                  </div>
                </div>

                <p className="flex items-center gap-1.5 text-sm text-brand-grey">
                  <MapPin className="size-3.5 shrink-0" />
                  {entreprise.country}
                </p>

                {entreprise.description ? (
                  <p className="line-clamp-2 text-sm text-brand-grey">{entreprise.description}</p>
                ) : null}

                <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 border-t pt-3 text-xs text-muted-foreground">
                  {entreprise.website ? (
                    <span className="flex min-w-0 items-center gap-1">
                      <Globe className="size-3.5 shrink-0" />
                      <span className="truncate">{entreprise.website}</span>
                    </span>
                  ) : null}
                  {entreprise.published_at ? (
                    <span className="ml-auto flex shrink-0 items-center gap-1">
                      <Calendar className="size-3.5 shrink-0" />
                      Publiée le {new Date(entreprise.published_at).toLocaleDateString("fr-FR")}
                    </span>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {entreprises.length > 0 && hasNextPage ? (
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
