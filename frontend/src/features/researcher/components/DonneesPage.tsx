import { Scale } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { EntreprisePublieePublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { CarbonSummary, ScoreSummary } from "@/shared/esg/EsgSummary";
import { uneDecimale } from "@/shared/format/etatPosition";
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
import { MAX_ENTREPRISES_COMPARAISON, useTableEntreprisesChercheur } from "../api";

/** Entreprises publiées : les données sur lesquelles construire une analyse (voir AnalysesPage).
 * Table de données (tâche 5.18) : identité, secteur, pays et score global. Les scores E/S/G, les
 * émissions et la fiche sont dans le tiroir. La case de la première colonne (ou le bouton du
 * tiroir) ajoute l'entreprise à la comparaison, avec le même plafond que le serveur. */
export function DonneesPage() {
  const { data, isLoading, isError } = useTableEntreprisesChercheur();
  const [selection, setSelection] = useState<string[]>([]);
  const [ouverteId, setOuverteId] = useState<string | null>(null);
  const navigate = useNavigate();

  const plafondAtteint = selection.length >= MAX_ENTREPRISES_COMPARAISON;

  const basculer = useCallback((id: string) => {
    setSelection((courante) => {
      if (courante.includes(id)) return courante.filter((v) => v !== id);
      // Plafond serveur (app/investor/entreprises.py::_MAX_ENTREPRISES_COMPARAISON) — refusé ici
      // plutôt que via une erreur générique après avoir déjà cliqué sur « Comparer ».
      if (courante.length >= MAX_ENTREPRISES_COMPARAISON) return courante;
      return [...courante, id];
    });
  }, []);

  const colonnes = useMemo<ColonneTable<EntreprisePublieePublic>[]>(
    () => [
      {
        id: "comparer",
        entete: "Comparer",
        masquable: false,
        alignement: "centre",
        cellule: (e) => {
          const cochee = selection.includes(e.id);
          return (
            <input
              type="checkbox"
              aria-label={`Sélectionner ${e.name} pour comparaison`}
              checked={cochee}
              disabled={!cochee && plafondAtteint}
              onClick={(ev) => ev.stopPropagation()}
              onChange={() => basculer(e.id)}
              className="size-4 accent-primary"
            />
          );
        },
      },
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
            {e.score.global_score != null ? uneDecimale(e.score.global_score) : "—"}
          </span>
        ),
      },
    ],
    [selection, plafondAtteint, basculer],
  );

  const ouverte = data?.find((e) => e.id === ouverteId) ?? null;
  const ouverteSelectionnee = ouverte ? selection.includes(ouverte.id) : false;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Données"
        description="Entreprises publiées — score ESG et émissions Scope 1/2/3, base de toute analyse."
        action={
          selection.length >= 2 ? (
            <Button onClick={() => navigate(`/researcher/comparaison?ids=${selection.join(",")}`)}>
              <Scale className="mr-2 size-4" />
              Comparer ({selection.length})
            </Button>
          ) : undefined
        }
      />

      {plafondAtteint ? (
        <p className="text-sm text-muted-foreground">
          Maximum {MAX_ENTREPRISES_COMPARAISON} entreprises pour une comparaison — décochez-en une
          pour en choisir une autre.
        </p>
      ) : null}

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
        nomExport="donnees-entreprises"
        memoire="chercheur-donnees"
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
              <SheetSection titre="Entreprise">
                <SheetFields
                  champs={[
                    { libelle: "Description", valeur: ouverte.description },
                    { libelle: "Site officiel", valeur: ouverte.website },
                    {
                      libelle: "Publiée le",
                      valeur: ouverte.published_at
                        ? new Date(ouverte.published_at).toLocaleDateString("fr-FR")
                        : null,
                    },
                  ]}
                />
              </SheetSection>
            </SheetBody>
            <SheetFooter>
              <Button asChild size="sm">
                <Link to={`/researcher/entreprises/${ouverte.id}`}>Fiche complète</Link>
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={!ouverteSelectionnee && plafondAtteint}
                onClick={() => basculer(ouverte.id)}
              >
                {ouverteSelectionnee ? "Retirer de la comparaison" : "Ajouter à la comparaison"}
              </Button>
            </SheetFooter>
          </SheetContent>
        ) : null}
      </Sheet>
    </div>
  );
}
