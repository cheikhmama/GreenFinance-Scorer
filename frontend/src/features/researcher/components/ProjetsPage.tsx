import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { ProjetAffecte } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleStatutProjet, variantStatutProjet } from "@/shared/format/statutProjet";
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
import { useMyAssignedProjects } from "../api";

function dateFr(iso: string | null): string | null {
  return iso ? new Date(iso).toLocaleDateString("fr-FR") : null;
}

/** Projets sur lesquels le Chercheur est affecté — objectif, période et échéance viennent
 * directement de l'Institution (voir app/institution/models.py::Projet), jamais éditables ici.
 * Table de données (tâche 5.18) : description et objectif sont dans le tiroir. */
export function ProjetsPage() {
  const { data: projets, isLoading, isError } = useMyAssignedProjects();
  const [ouvertId, setOuvertId] = useState<string | null>(null);

  const colonnes = useMemo<ColonneTable<ProjetAffecte>[]>(
    () => [
      {
        id: "nom",
        entete: "Projet",
        masquable: false,
        valeurTri: (p) => p.name,
        cellule: (p) => <span className="font-semibold text-foreground">{p.name}</span>,
      },
      {
        id: "institution",
        entete: "Institution",
        valeurTri: (p) => p.institution_email,
        cellule: (p) => <span className="text-muted-foreground">{p.institution_email}</span>,
      },
      {
        id: "statut",
        entete: "Statut",
        alignement: "centre",
        valeurTri: (p) => libelleStatutProjet(p.status),
        cellule: (p) => (
          <Badge variant={variantStatutProjet(p.status)}>{libelleStatutProjet(p.status)}</Badge>
        ),
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
  const ouvert = projets?.find((p) => p.id === ouvertId) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mes projets"
        description="Projets qui vous sont affectés — objectif, échéances, périmètre et documents autorisés."
      />

      <DataTable
        libelle="Projets affectés"
        lignes={projets}
        colonnes={colonnes}
        cle={(p) => p.id}
        rechercheDans={(p) => `${p.name} ${p.institution_email} ${p.objective ?? ""}`}
        placeholderRecherche="Projet, institution, objectif…"
        filtres={[
          { id: "statut", libelle: "Statut", valeur: (p) => libelleStatutProjet(p.status) },
          { id: "institution", libelle: "Institution", valeur: (p) => p.institution_email },
        ]}
        triInitial={{ colonne: "nom", sens: "asc" }}
        surOuvrir={(p) => setOuvertId(p.id)}
        libelleLigne={(p) => p.name}
        ligneActive={ouvertId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucun projet ne vous est encore affecté — une institution doit d’abord vous inviter puis vous affecter à un projet."
        nomExport="mes-projets"
        memoire="chercheur-projets"
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
                    { libelle: "Objectif", valeur: ouvert.objective },
                    { libelle: "Description", valeur: ouvert.description },
                  ]}
                />
              </SheetSection>
              <SheetSection titre="Calendrier">
                <SheetFields
                  champs={[
                    { libelle: "Début", valeur: dateFr(ouvert.start_date) },
                    { libelle: "Fin prévue", valeur: dateFr(ouvert.planned_end_date) },
                    { libelle: "Échéance", valeur: dateFr(ouvert.deadline) },
                  ]}
                />
              </SheetSection>
            </SheetBody>
            <SheetFooter>
              <Button asChild size="sm">
                <Link to={`/researcher/projets/${ouvert.id}`}>Ouvrir le projet</Link>
              </Button>
            </SheetFooter>
          </SheetContent>
        ) : null}
      </Sheet>
    </div>
  );
}
