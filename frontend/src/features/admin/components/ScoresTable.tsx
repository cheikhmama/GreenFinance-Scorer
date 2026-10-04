import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { EntrepriseAvecScoreAdmin } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { uneDecimale } from "@/shared/format/etatPosition";
import { libellePays } from "@/shared/format/pays";
import { Button } from "@/shared/ui/button";
import { type ColonneTable, DataTable } from "@/shared/ui/data-table";
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
import { useTableScores } from "../api";

const note = (v: number | null) => (v === null ? "—" : uneDecimale(v));

/** Scores ESG des entreprises publiées (tâche 5.17) : le score global dans la table, le détail
 * par pilier dans le tiroir. */
export function ScoresTable() {
  const { data, isLoading, isError } = useTableScores();
  const [ouverteId, setOuverteId] = useState<string | null>(null);

  const colonnes = useMemo<ColonneTable<EntrepriseAvecScoreAdmin>[]>(
    () => [
      {
        id: "nom",
        entete: "Entreprise",
        masquable: false,
        valeurTri: (e) => e.name,
        cellule: (e) => <span className="font-semibold text-foreground">{e.name}</span>,
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
        entete: "Score global",
        alignement: "droite",
        valeurTri: (e) => e.global_score,
        cellule: (e) => <span className="font-mono font-semibold">{note(e.global_score)}</span>,
      },
    ],
    [],
  );

  const ouverte = data?.find((e) => e.id === ouverteId) ?? null;

  return (
    <>
      <DataTable
        libelle="Scores ESG des entreprises publiées"
        lignes={data}
        colonnes={colonnes}
        cle={(e) => e.id}
        rechercheDans={(e) => `${e.name} ${e.sector} ${libellePays(e.country)}`}
        placeholderRecherche="Nom, secteur, pays…"
        filtres={[
          { id: "secteur", libelle: "Secteur", valeur: (e) => e.sector },
          { id: "pays", libelle: "Pays", valeur: (e) => libellePays(e.country) },
        ]}
        triInitial={{ colonne: "score", sens: "desc" }}
        surOuvrir={(e) => setOuverteId(e.id)}
        libelleLigne={(e) => e.name}
        ligneActive={ouverteId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucune entreprise publiée n’a encore de score."
        nomExport="scores-esg"
        memoire="admin-scores"
      />
      <Sheet open={ouverte !== null} onOpenChange={(o) => !o && setOuverteId(null)}>
        {ouverte ? (
          <SheetContent>
            <SheetHeader>
              <SheetTitle>{ouverte.name}</SheetTitle>
              <SheetDescription>
                {ouverte.sector} · {libellePays(ouverte.country)}
              </SheetDescription>
            </SheetHeader>
            <SheetBody>
              <SheetSection titre="Score officiel">
                <SheetFields
                  champs={[
                    {
                      libelle: "Global",
                      valeur: (
                        <span className="font-mono font-semibold">
                          {note(ouverte.global_score)}/100
                        </span>
                      ),
                    },
                    {
                      libelle: "Environnement",
                      valeur: (
                        <span className="font-mono">{note(ouverte.environmental_score)}</span>
                      ),
                    },
                    {
                      libelle: "Social",
                      valeur: <span className="font-mono">{note(ouverte.social_score)}</span>,
                    },
                    {
                      libelle: "Gouvernance",
                      valeur: <span className="font-mono">{note(ouverte.governance_score)}</span>,
                    },
                  ]}
                />
              </SheetSection>
            </SheetBody>
            <SheetFooter>
              <Button asChild size="sm">
                <Link to={`/admin/entreprises/${ouverte.id}`}>Ouvrir la fiche</Link>
              </Button>
            </SheetFooter>
          </SheetContent>
        ) : null}
      </Sheet>
    </>
  );
}
