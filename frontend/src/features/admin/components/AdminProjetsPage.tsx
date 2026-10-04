import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type {
  ProjectStatus,
  ProjetAdmin,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleStatutProjet, variantStatutProjet } from "@/shared/format/statutProjet";
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
import { useTableProjets } from "../api";

const STATUTS: ProjectStatus[] = ["OUVERT", "CLOTURE"];

function dateFr(iso: string | null): string | null {
  return iso ? new Date(iso).toLocaleDateString("fr-FR") : null;
}

/** Tous les projets Institution (table, tâche 5.17) ; `?statut=` présélectionne le filtre (liens
 * « Projets ouverts / clôturés » du tableau de bord). */
export function AdminProjetsPage() {
  const { data, isLoading, isError } = useTableProjets();
  const [searchParams] = useSearchParams();
  const statutUrl = searchParams.get("statut") as ProjectStatus | null;
  const [ouvertId, setOuvertId] = useState<string | null>(null);

  const colonnes = useMemo<ColonneTable<ProjetAdmin>[]>(
    () => [
      {
        id: "projet",
        entete: "Projet",
        masquable: false,
        valeurTri: (p) => p.name,
        cellule: (p) => <span className="font-semibold text-foreground">{p.name}</span>,
      },
      {
        id: "institution",
        entete: "Institution",
        valeurTri: (p) => p.institution_email,
        cellule: (p) => <span className="font-mono text-[12.5px]">{p.institution_email}</span>,
      },
      {
        id: "chercheurs",
        entete: "Chercheurs",
        alignement: "droite",
        valeurTri: (p) => p.researcher_count,
        cellule: (p) => <span className="font-mono">{p.researcher_count}</span>,
      },
      {
        id: "echeance",
        entete: "Échéance",
        alignement: "droite",
        valeurTri: (p) => p.deadline,
        cellule: (p) => <span className="font-mono">{dateFr(p.deadline) ?? "—"}</span>,
      },
    ],
    [],
  );
  const ouvert = data?.find((p) => p.id === ouvertId) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader title="Projets" description="Tous les projets des institutions." />
      <DataTable
        libelle="Projets"
        lignes={data}
        colonnes={colonnes}
        cle={(p) => p.id}
        rechercheDans={(p) => `${p.name} ${p.institution_email}`}
        placeholderRecherche="Projet, institution…"
        filtres={[
          { id: "statut", libelle: "Statut", valeur: (p) => libelleStatutProjet(p.status) },
          { id: "institution", libelle: "Institution", valeur: (p) => p.institution_email },
        ]}
        filtresInitiaux={
          statutUrl && STATUTS.includes(statutUrl)
            ? { statut: [libelleStatutProjet(statutUrl)] }
            : undefined
        }
        triInitial={{ colonne: "echeance", sens: "asc" }}
        surOuvrir={(p) => setOuvertId(p.id)}
        libelleLigne={(p) => p.name}
        ligneActive={ouvertId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucun projet."
        nomExport="projets"
        memoire="admin-projets"
      />
      <Sheet open={ouvert !== null} onOpenChange={(o) => !o && setOuvertId(null)}>
        {ouvert ? (
          <SheetContent>
            <SheetHeader>
              <SheetTitle>{ouvert.name}</SheetTitle>
              <SheetDescription>{ouvert.institution_email}</SheetDescription>
              <Badge variant={variantStatutProjet(ouvert.status)} className="w-fit">
                {libelleStatutProjet(ouvert.status)}
              </Badge>
            </SheetHeader>
            <SheetBody>
              <SheetSection titre="Projet">
                <SheetFields
                  champs={[
                    { libelle: "Statut", valeur: libelleStatutProjet(ouvert.status) },
                    {
                      libelle: "Chercheurs affectés",
                      valeur: <span className="font-mono">{ouvert.researcher_count}</span>,
                    },
                    { libelle: "Créé le", valeur: dateFr(ouvert.created_at) },
                    { libelle: "Échéance", valeur: dateFr(ouvert.deadline) },
                    { libelle: "Clôturé le", valeur: dateFr(ouvert.closed_at) },
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
