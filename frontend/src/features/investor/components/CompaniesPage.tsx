import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { EntreprisePublieePublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { libellePays } from "@/shared/format/pays";
import { Button } from "@/shared/ui/button";
import { type ColonneTable, DataTable } from "@/shared/ui/data-table";
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
import { useTableEntreprisesPubliees } from "../api";

function dateFr(iso: string | null): string | null {
  return iso ? new Date(iso).toLocaleDateString("fr-FR") : null;
}

/** Entreprises publiées (table de données, tâche 5.18) : identité, secteur, pays et date de
 * publication — jamais le score ESG, les scores E/S/G ni le montant minimum ici : ces données
 * détaillées restent réservées à la fiche dédiée (voir CompanyDetailPage.tsx), ouverte depuis le
 * tiroir. Le secteur passé dans l'URL (?secteur=..., depuis le Dashboard) présélectionne le
 * filtre Secteur. */
export function CompaniesPage() {
  const { data, isLoading, isError } = useTableEntreprisesPubliees();
  const [searchParams] = useSearchParams();
  const secteurUrl = searchParams.get("secteur");
  const [ouverteId, setOuverteId] = useState<string | null>(null);

  const colonnes = useMemo<ColonneTable<EntreprisePublieePublic>[]>(
    () => [
      {
        id: "nom",
        entete: "Entreprise",
        masquable: false,
        valeurTri: (e) => e.name,
        cellule: (e) => (
          <span className="flex items-center gap-2.5 font-semibold text-foreground">
            <CompanyAvatar nom={e.name} logo={e.logo} className="size-6 shrink-0 text-[10px]" />
            {e.name}
          </span>
        ),
      },
      {
        id: "secteur",
        entete: "Secteur",
        valeurTri: (e) => e.sector,
        cellule: (e) => <span className="text-muted-foreground">{e.sector}</span>,
      },
      {
        id: "pays",
        entete: "Pays",
        valeurTri: (e) => libellePays(e.country),
        cellule: (e) => libellePays(e.country),
      },
      {
        id: "publiee",
        entete: "Publiée le",
        alignement: "droite",
        valeurTri: (e) => e.published_at,
        cellule: (e) => <span className="font-mono">{dateFr(e.published_at) ?? "—"}</span>,
      },
    ],
    [],
  );
  const ouverte = data?.find((e) => e.id === ouverteId) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Entreprises"
        description="Parcourez les entreprises dont les données ont été validées et publiées. Ouvrez une ligne pour accéder à sa fiche ESG complète."
      />
      <DataTable
        libelle="Entreprises publiées"
        lignes={data}
        colonnes={colonnes}
        cle={(e) => e.id}
        rechercheDans={(e) => `${e.name} ${e.sector} ${libellePays(e.country)} ${e.ticker ?? ""}`}
        placeholderRecherche="Nom, secteur, pays…"
        filtres={[
          { id: "secteur", libelle: "Secteur", valeur: (e) => e.sector },
          { id: "pays", libelle: "Pays", valeur: (e) => libellePays(e.country) },
        ]}
        filtresInitiaux={secteurUrl ? { secteur: [secteurUrl] } : undefined}
        triInitial={{ colonne: "nom", sens: "asc" }}
        surOuvrir={(e) => setOuverteId(e.id)}
        libelleLigne={(e) => e.name}
        ligneActive={ouverteId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucune entreprise publiée pour l’instant."
        nomExport="entreprises-publiees"
        memoire="investor-entreprises"
      />
      <Sheet open={ouverte !== null} onOpenChange={(o) => !o && setOuverteId(null)}>
        {ouverte ? (
          <SheetContent>
            <SheetHeader>
              <div className="flex items-start gap-3">
                <CompanyAvatar
                  nom={ouverte.name}
                  logo={ouverte.logo}
                  className="size-11 shrink-0"
                />
                <div className="flex min-w-0 flex-col gap-1.5">
                  <SheetTitle>{ouverte.name}</SheetTitle>
                  <SheetDescription>
                    {ouverte.sector} · {libellePays(ouverte.country)}
                  </SheetDescription>
                </div>
              </div>
            </SheetHeader>
            <SheetBody>
              {ouverte.description ? (
                <SheetSection titre="Présentation">
                  <p className="text-sm text-muted-foreground">{ouverte.description}</p>
                </SheetSection>
              ) : null}
              <SheetSection titre="Informations générales">
                <SheetFields
                  champs={[
                    { libelle: "Publiée le", valeur: dateFr(ouverte.published_at) },
                    { libelle: "Site officiel", valeur: ouverte.website },
                    { libelle: "Ticker", valeur: ouverte.ticker },
                    {
                      libelle: "ISIN · LEI",
                      valeur: [ouverte.isin, ouverte.lei].filter(Boolean).join(" · ") || null,
                    },
                  ]}
                />
              </SheetSection>
            </SheetBody>
            <SheetFooter>
              <Button asChild size="sm">
                <Link to={`/investor/entreprises/${ouverte.id}`}>Voir la fiche ESG</Link>
              </Button>
            </SheetFooter>
          </SheetContent>
        ) : null}
      </Sheet>
    </div>
  );
}
