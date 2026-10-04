import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type {
  AnalyseAdmin,
  AnalysisStatus,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleStatutAnalyse, variantStatutAnalyse } from "@/shared/format/statutAnalyse";
import { Badge } from "@/shared/ui/badge";
import { type ColonneTable, DataTable } from "@/shared/ui/data-table";
import { PageHeader } from "@/shared/ui/page-header";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFields,
  SheetHeader,
  SheetSection,
  SheetTitle,
} from "@/shared/ui/sheet";
import { useTableAnalyses } from "../api";

function dateFr(iso: string | null): string | null {
  return iso ? new Date(iso).toLocaleDateString("fr-FR") : null;
}

/** Toutes les analyses Chercheur, toutes versions (table, tâche 5.17) ; `?statut=` présélectionne
 * le filtre (liens « soumises / correction demandée » du tableau de bord). */
export function AdminAnalysesPage() {
  const { data, isLoading, isError } = useTableAnalyses();
  const [searchParams] = useSearchParams();
  const statutUrl = searchParams.get("statut") as AnalysisStatus | null;
  const [ouvertId, setOuvertId] = useState<string | null>(null);

  const colonnes = useMemo<ColonneTable<AnalyseAdmin>[]>(
    () => [
      {
        id: "analyse",
        entete: "Analyse",
        masquable: false,
        valeurTri: (a) => a.title,
        cellule: (a) => <span className="font-semibold text-foreground">{a.title}</span>,
      },
      {
        id: "chercheur",
        entete: "Chercheur",
        valeurTri: (a) => a.researcher_email,
        cellule: (a) => <span className="font-mono text-[12.5px]">{a.researcher_email}</span>,
      },
      {
        id: "projet",
        entete: "Projet",
        valeurTri: (a) => a.project_name,
        cellule: (a) => <span className="text-muted-foreground">{a.project_name}</span>,
      },
      {
        id: "version",
        entete: "Version",
        alignement: "droite",
        valeurTri: (a) => a.version,
        cellule: (a) => <span className="font-mono">{a.version}</span>,
      },
    ],
    [],
  );
  const ouvert = data?.find((a) => a.id === ouvertId) ?? null;
  const statutInitial = statutUrl ? libelleStatutAnalyse(statutUrl) : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analyses"
        description="Toutes les analyses des chercheurs, toutes versions."
      />
      <DataTable
        libelle="Analyses"
        lignes={data}
        colonnes={colonnes}
        cle={(a) => a.id}
        rechercheDans={(a) => `${a.title} ${a.researcher_email} ${a.project_name}`}
        placeholderRecherche="Titre, chercheur, projet…"
        filtres={[
          { id: "statut", libelle: "Statut", valeur: (a) => libelleStatutAnalyse(a.status) },
          { id: "projet", libelle: "Projet", valeur: (a) => a.project_name },
        ]}
        filtresInitiaux={statutInitial ? { statut: [statutInitial] } : undefined}
        triInitial={{ colonne: "analyse", sens: "asc" }}
        surOuvrir={(a) => setOuvertId(a.id)}
        libelleLigne={(a) => a.title}
        ligneActive={ouvertId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucune analyse."
        nomExport="analyses"
        memoire="admin-analyses"
      />
      <Sheet open={ouvert !== null} onOpenChange={(o) => !o && setOuvertId(null)}>
        {ouvert ? (
          <SheetContent>
            <SheetHeader>
              <SheetTitle>{ouvert.title}</SheetTitle>
              <SheetDescription>
                {ouvert.project_name} · version {ouvert.version}
              </SheetDescription>
              <Badge variant={variantStatutAnalyse(ouvert.status)} className="w-fit">
                {libelleStatutAnalyse(ouvert.status)}
              </Badge>
            </SheetHeader>
            <SheetBody>
              <SheetSection titre="Workflow">
                <SheetFields
                  champs={[
                    { libelle: "Statut", valeur: libelleStatutAnalyse(ouvert.status) },
                    { libelle: "Chercheur", valeur: ouvert.researcher_email },
                    { libelle: "Créée le", valeur: dateFr(ouvert.created_at) },
                    { libelle: "Soumise le", valeur: dateFr(ouvert.submitted_at) },
                    { libelle: "Décidée le", valeur: dateFr(ouvert.decided_at) },
                  ]}
                />
              </SheetSection>
            </SheetBody>
          </SheetContent>
        ) : null}
      </Sheet>
    </div>
  );
}
