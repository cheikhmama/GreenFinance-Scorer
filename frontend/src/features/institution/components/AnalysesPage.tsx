import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { AnalyseInstitutionPublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleStatutAnalyse, variantStatutAnalyse } from "@/shared/format/statutAnalyse";
import { Badge } from "@/shared/ui/badge";
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
import { useMyAnalysesForInstitution } from "../api";

const dateFr = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("fr-FR") : null);

/** Analyses reçues, tous projets confondus (table de données, tâche 5.18). Les analyses SOUMISE
 * (en attente de décision) remontent en premier : c'est le tri initial de la colonne Statut. */
export function AnalysesPage() {
  const { data: analyses, isLoading, isError } = useMyAnalysesForInstitution();
  const [ouverteId, setOuverteId] = useState<string | null>(null);
  const aDecider = analyses?.filter((a) => a.status === "SOUMISE").length ?? 0;

  const colonnes = useMemo<ColonneTable<AnalyseInstitutionPublic>[]>(
    () => [
      {
        id: "titre",
        entete: "Analyse",
        masquable: false,
        valeurTri: (a) => a.title,
        cellule: (a) => <span className="font-semibold text-foreground">{a.title}</span>,
      },
      {
        id: "projet",
        entete: "Projet",
        valeurTri: (a) => a.project_name,
        cellule: (a) => <span className="text-muted-foreground">{a.project_name}</span>,
      },
      {
        id: "statut",
        entete: "Statut",
        alignement: "centre",
        // « SOUMISE » d'abord : 0 avant 1 en tri croissant.
        valeurTri: (a) => `${a.status === "SOUMISE" ? 0 : 1}-${libelleStatutAnalyse(a.status)}`,
        valeurExport: (a) => libelleStatutAnalyse(a.status),
        cellule: (a) => (
          <Badge variant={variantStatutAnalyse(a.status)}>{libelleStatutAnalyse(a.status)}</Badge>
        ),
      },
      {
        id: "soumise",
        entete: "Soumise le",
        alignement: "droite",
        valeurTri: (a) => a.submitted_at,
        cellule: (a) => <span className="font-mono">{dateFr(a.submitted_at) ?? "—"}</span>,
      },
    ],
    [],
  );
  const ouverte = analyses?.find((a) => a.id === ouverteId) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analyses"
        description="Toutes les analyses reçues de vos chercheurs, tous projets confondus."
      />
      {aDecider > 0 ? (
        <p className="rounded-xl border border-warning-border bg-warning-soft p-4 text-sm text-warning">
          {aDecider} analyse{aDecider > 1 ? "s" : ""} en attente de votre décision.
        </p>
      ) : null}
      <DataTable
        libelle="Analyses reçues"
        lignes={analyses}
        colonnes={colonnes}
        cle={(a) => a.id}
        rechercheDans={(a) => `${a.title} ${a.project_name}`}
        placeholderRecherche="Titre, projet…"
        filtres={[
          { id: "statut", libelle: "Statut", valeur: (a) => libelleStatutAnalyse(a.status) },
          { id: "projet", libelle: "Projet", valeur: (a) => a.project_name },
        ]}
        triInitial={{ colonne: "statut", sens: "asc" }}
        surOuvrir={(a) => setOuverteId(a.id)}
        libelleLigne={(a) => a.title}
        ligneActive={ouverteId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucune analyse reçue pour l’instant — elles apparaîtront ici dès qu’un chercheur affecté à l’un de vos projets en soumettra une."
        nomExport="analyses-recues"
        memoire="institution-analyses"
      />
      <Sheet open={ouverte !== null} onOpenChange={(o) => !o && setOuverteId(null)}>
        {ouverte ? (
          <SheetContent>
            <SheetHeader>
              <SheetTitle>{ouverte.title}</SheetTitle>
              <SheetDescription>{ouverte.project_name}</SheetDescription>
              <Badge variant={variantStatutAnalyse(ouverte.status)} className="w-fit">
                {libelleStatutAnalyse(ouverte.status)}
              </Badge>
            </SheetHeader>
            <SheetBody>
              <SheetSection titre="Suivi">
                <SheetFields
                  champs={[
                    {
                      libelle: "Version",
                      valeur: <span className="font-mono">{ouverte.version}</span>,
                    },
                    { libelle: "Créée le", valeur: dateFr(ouverte.created_at) },
                    { libelle: "Soumise le", valeur: dateFr(ouverte.submitted_at) },
                  ]}
                />
              </SheetSection>
            </SheetBody>
            <SheetFooter>
              <Button asChild size="sm">
                <Link to={`/institution/analyses/${ouverte.id}`}>
                  {ouverte.status === "SOUMISE" ? "Rendre la décision" : "Ouvrir l’analyse"}
                </Link>
              </Button>
              <Button asChild size="sm" variant="outline">
                <Link to={`/institution/projets/${ouverte.project_id}`}>Voir le projet</Link>
              </Button>
            </SheetFooter>
          </SheetContent>
        ) : null}
      </Sheet>
    </div>
  );
}
