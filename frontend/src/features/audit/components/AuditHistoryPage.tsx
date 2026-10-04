import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { AvisHistorique } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleDecisionAudit } from "@/shared/format/decisionAudit";
import { libelleTypeRapport, titreDeclaration } from "@/shared/format/typeRapport";
import { PageShell } from "@/shared/layout/PageShell";
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
import { useAuditHistory } from "../api";

const titre = (a: AvisHistorique) =>
  titreDeclaration({ type: a.report_type, fiscal_year: a.fiscal_year, version: a.report_version });

/** Avis déjà rendus par l'Auditeur (table de données, tâche 5.18) ; commentaire et date dans le
 * tiroir. */
export function AuditHistoryPage() {
  const { data, isLoading, isError } = useAuditHistory();
  const [ouvertId, setOuvertId] = useState<string | null>(null);

  const colonnes = useMemo<ColonneTable<AvisHistorique>[]>(
    () => [
      {
        id: "entreprise",
        entete: "Entreprise",
        masquable: false,
        valeurTri: (a) => a.company_name,
        cellule: (a) => <span className="font-semibold text-foreground">{a.company_name}</span>,
      },
      {
        id: "exercice",
        entete: "Exercice",
        alignement: "droite",
        valeurTri: (a) => a.fiscal_year,
        cellule: (a) => <span className="font-mono">{a.fiscal_year ?? "—"}</span>,
      },
      {
        id: "type",
        entete: "Type de rapport",
        valeurTri: (a) => libelleTypeRapport(a.report_type),
        cellule: (a) => libelleTypeRapport(a.report_type),
      },
      {
        id: "avis",
        entete: "Avis",
        valeurTri: (a) => libelleDecisionAudit(a.decision),
        cellule: (a) => libelleDecisionAudit(a.decision),
      },
    ],
    [],
  );
  const ouvert = data?.find((a) => a.id === ouvertId) ?? null;

  return (
    <PageShell
      title="Historique de mes avis"
      description="Dossiers sur lesquels un avis a déjà été rendu."
    >
      <DataTable
        libelle="Avis rendus"
        lignes={data}
        colonnes={colonnes}
        cle={(a) => a.id}
        rechercheDans={(a) => `${a.company_name} ${a.comment ?? ""}`}
        placeholderRecherche="Entreprise, commentaire…"
        filtres={[
          { id: "avis", libelle: "Avis", valeur: (a) => libelleDecisionAudit(a.decision) },
          {
            id: "exercice",
            libelle: "Exercice",
            valeur: (a) => (a.fiscal_year ? String(a.fiscal_year) : null),
          },
        ]}
        triInitial={{ colonne: "entreprise", sens: "asc" }}
        surOuvrir={(a) => setOuvertId(a.id)}
        libelleLigne={(a) => `${a.company_name}, ${titre(a)}`}
        ligneActive={ouvertId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucun avis rendu pour l’instant."
        nomExport="avis-rendus"
        memoire="audit-historique"
      />
      <Sheet open={ouvert !== null} onOpenChange={(o) => !o && setOuvertId(null)}>
        {ouvert ? (
          <SheetContent>
            <SheetHeader>
              <SheetTitle>{ouvert.company_name}</SheetTitle>
              <SheetDescription>{titre(ouvert)}</SheetDescription>
            </SheetHeader>
            <SheetBody>
              <SheetSection titre="Avis">
                <SheetFields
                  champs={[
                    { libelle: "Décision", valeur: libelleDecisionAudit(ouvert.decision) },
                    {
                      libelle: "Rendu le",
                      valeur: new Date(ouvert.submitted_at).toLocaleDateString("fr-FR"),
                    },
                    { libelle: "Commentaire", valeur: ouvert.comment },
                  ]}
                />
              </SheetSection>
            </SheetBody>
            <SheetFooter>
              <Button asChild size="sm" variant="outline">
                <Link to={`/audit/rapports/${ouvert.report_id}`}>Voir le dossier</Link>
              </Button>
            </SheetFooter>
          </SheetContent>
        ) : null}
      </Sheet>
    </PageShell>
  );
}
