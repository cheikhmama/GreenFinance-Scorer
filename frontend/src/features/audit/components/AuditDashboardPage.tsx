import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { DossierAuditeur } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import { libelleTypeRapport, titreDeclaration } from "@/shared/format/typeRapport";
import { PageShell } from "@/shared/layout/PageShell";
import { Badge } from "@/shared/ui/badge";
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
import { useAssignedReports } from "../api";

function dateFr(iso: string | null): string | null {
  return iso ? new Date(iso).toLocaleDateString("fr-FR") : null;
}

/** Dossiers affectés à l'Auditeur, en attente d'avis (table de données, tâche 5.18). */
export function AuditDashboardPage() {
  const { data, isLoading, isError } = useAssignedReports();
  const [ouvertId, setOuvertId] = useState<string | null>(null);

  const colonnes = useMemo<ColonneTable<DossierAuditeur>[]>(
    () => [
      {
        id: "entreprise",
        entete: "Entreprise",
        masquable: false,
        valeurTri: (d) => d.company_name,
        cellule: (d) => <span className="font-semibold text-foreground">{d.company_name}</span>,
      },
      {
        id: "secteur",
        entete: "Secteur",
        valeurTri: (d) => d.company_sector,
        cellule: (d) => <span className="text-muted-foreground">{d.company_sector}</span>,
      },
      {
        id: "exercice",
        entete: "Exercice",
        alignement: "droite",
        valeurTri: (d) => d.fiscal_year,
        cellule: (d) => <span className="font-mono">{d.fiscal_year ?? "—"}</span>,
      },
      {
        id: "type",
        entete: "Type de rapport",
        valeurTri: (d) => libelleTypeRapport(d.type),
        cellule: (d) => libelleTypeRapport(d.type),
      },
      {
        id: "depose",
        entete: "Déposé le",
        alignement: "droite",
        valeurTri: (d) => d.submitted_at,
        cellule: (d) => <span className="font-mono">{dateFr(d.submitted_at) ?? "—"}</span>,
      },
    ],
    [],
  );
  const ouvert = data?.find((d) => d.id === ouvertId) ?? null;

  return (
    <PageShell
      title="Dossiers affectés"
      description="Rapports qui vous ont été affectés, en attente de votre avis."
    >
      <DataTable
        libelle="Dossiers en attente d’avis"
        lignes={data}
        colonnes={colonnes}
        cle={(d) => d.id}
        rechercheDans={(d) => `${d.company_name} ${d.company_sector} ${d.fiscal_year ?? ""}`}
        placeholderRecherche="Entreprise, secteur, exercice…"
        filtres={[
          { id: "secteur", libelle: "Secteur", valeur: (d) => d.company_sector },
          { id: "type", libelle: "Type", valeur: (d) => libelleTypeRapport(d.type) },
        ]}
        triInitial={{ colonne: "depose", sens: "asc" }}
        surOuvrir={(d) => setOuvertId(d.id)}
        libelleLigne={(d) => `${d.company_name}, ${titreDeclaration(d)}`}
        ligneActive={ouvertId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucun dossier en attente d’avis pour l’instant."
        nomExport="dossiers-affectes"
        memoire="audit-dossiers"
      />
      <Sheet open={ouvert !== null} onOpenChange={(o) => !o && setOuvertId(null)}>
        {ouvert ? (
          <SheetContent>
            <SheetHeader>
              <SheetTitle>{ouvert.company_name}</SheetTitle>
              <SheetDescription>{titreDeclaration(ouvert)}</SheetDescription>
              <Badge variant={variantStatutRapport(ouvert.status)} className="w-fit">
                {libelleStatutRapport(ouvert.status)}
              </Badge>
            </SheetHeader>
            <SheetBody>
              <SheetSection titre="Dossier">
                <SheetFields
                  champs={[
                    { libelle: "Secteur", valeur: ouvert.company_sector },
                    { libelle: "Déposé le", valeur: dateFr(ouvert.submitted_at) },
                    {
                      libelle: "Version",
                      valeur: <span className="font-mono">{ouvert.version}</span>,
                    },
                    { libelle: "Fichier", valeur: ouvert.original_filename },
                  ]}
                />
              </SheetSection>
            </SheetBody>
            <SheetFooter>
              <Button asChild size="sm">
                <Link to={`/audit/rapports/${ouvert.id}`}>Examiner le dossier</Link>
              </Button>
            </SheetFooter>
          </SheetContent>
        ) : null}
      </Sheet>
    </PageShell>
  );
}
