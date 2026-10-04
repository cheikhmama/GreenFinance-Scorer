import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { EntreprisePublieePublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { CarbonSummary, ScoreSummary } from "@/shared/esg/EsgSummary";
import { formatScore } from "@/shared/format/etatPosition";
import { formatValeur } from "@/shared/format/indicateurs";
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
import { useTableEntreprisesInstitution } from "../api";

const tonnes = (valeur: number | null) => (valeur === null ? "—" : formatValeur(valeur, "tCO2e"));

/** Catalogue des entreprises publiées (table de données, tâche 5.18) : identité, secteur, pays,
 * score global et Scope 1 ; le détail ESG et carbone complet est dans le tiroir. Pas de sélection
 * de comparaison : comparer est un geste d'analyse, pas un geste de décision institutionnelle. */
export function CompaniesPage() {
  const { data, isLoading, isError } = useTableEntreprisesInstitution();
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
        id: "score",
        entete: "Score ESG",
        alignement: "droite",
        valeurTri: (e) => e.score.global_score,
        cellule: (e) => (
          <span className="font-mono font-semibold tabular-nums">
            {formatScore(e.score.global_score)}
          </span>
        ),
      },
      {
        id: "scope1",
        entete: "Scope 1",
        alignement: "droite",
        valeurTri: (e) => e.carbon.scope_1,
        cellule: (e) => <span className="font-mono tabular-nums">{tonnes(e.carbon.scope_1)}</span>,
      },
    ],
    [],
  );
  const ouverte = data?.find((e) => e.id === ouverteId) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Entreprises"
        description="Entreprises publiées — score ESG et émissions Scope 1/2/3, base de tout périmètre de projet."
      />
      <DataTable
        libelle="Entreprises publiées"
        lignes={data}
        colonnes={colonnes}
        cle={(e) => e.id}
        rechercheDans={(e) => `${e.name} ${e.sector} ${libellePays(e.country)}`}
        placeholderRecherche="Nom, secteur, pays…"
        filtres={[
          { id: "secteur", libelle: "Secteur", valeur: (e) => e.sector },
          { id: "pays", libelle: "Pays", valeur: (e) => libellePays(e.country) },
        ]}
        triInitial={{ colonne: "nom", sens: "asc" }}
        surOuvrir={(e) => setOuverteId(e.id)}
        libelleLigne={(e) => e.name}
        ligneActive={ouverteId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucune entreprise publiée pour l’instant."
        nomExport="entreprises-publiees"
        memoire="institution-entreprises"
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
              <SheetSection titre="Score ESG">
                <ScoreSummary score={ouverte.score} />
              </SheetSection>
              <SheetSection titre="Émissions">
                <CarbonSummary carbone={ouverte.carbon} />
              </SheetSection>
              <SheetSection titre="Identité">
                <SheetFields
                  champs={[
                    {
                      libelle: "Publiée le",
                      valeur: ouverte.published_at
                        ? new Date(ouverte.published_at).toLocaleDateString("fr-FR")
                        : null,
                    },
                    { libelle: "Site officiel", valeur: ouverte.website },
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
                <Link to={`/institution/entreprises/${ouverte.id}`}>Ouvrir la fiche</Link>
              </Button>
            </SheetFooter>
          </SheetContent>
        ) : null}
      </Sheet>
    </div>
  );
}
