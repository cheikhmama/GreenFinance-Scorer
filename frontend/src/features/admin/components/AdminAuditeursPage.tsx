import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { ChargeAuditeurAdmin } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { type ColonneTable, DataTable } from "@/shared/ui/data-table";
import { PageHeader } from "@/shared/ui/page-header";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetFields,
  SheetFooter,
  SheetHeader,
  SheetSection,
  SheetTitle,
} from "@/shared/ui/sheet";
import { useTableAuditeurs } from "../api";

const nombre = (n: number) => <span className="font-mono tabular-nums">{n}</span>;

/** Charge de travail par Auditeur actif (table de données, tâche 5.17). */
export function AdminAuditeursPage() {
  const { data, isLoading, isError } = useTableAuditeurs();
  const [ouvertId, setOuvertId] = useState<string | null>(null);

  const colonnes = useMemo<ColonneTable<ChargeAuditeurAdmin>[]>(
    () => [
      {
        id: "auditeur",
        entete: "Auditeur",
        masquable: false,
        valeurTri: (a) => a.email,
        cellule: (a) => <span className="font-semibold text-foreground">{a.email}</span>,
      },
      {
        id: "affectes",
        entete: "Dossiers affectés",
        alignement: "droite",
        valeurTri: (a) => a.assigned_reports,
        cellule: (a) => nombre(a.assigned_reports),
      },
      {
        id: "retard",
        entete: "En retard",
        alignement: "droite",
        valeurTri: (a) => a.overdue_reports,
        cellule: (a) => nombre(a.overdue_reports),
      },
      {
        id: "avis",
        entete: "Avis rendus",
        alignement: "droite",
        valeurTri: (a) => a.opinions_submitted,
        cellule: (a) => nombre(a.opinions_submitted),
      },
    ],
    [],
  );
  const ouvert = data?.find((a) => a.auditor_id === ouvertId) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Auditeurs"
        description="Charge de travail par auditeur actif : dossiers affectés, en retard et avis rendus."
      />
      <DataTable
        libelle="Auditeurs"
        lignes={data}
        colonnes={colonnes}
        cle={(a) => a.auditor_id}
        rechercheDans={(a) => a.email}
        placeholderRecherche="E-mail de l’auditeur…"
        filtres={[
          {
            id: "retard",
            libelle: "Retard",
            valeur: (a) => (a.overdue_reports > 0 ? "Avec retard" : "À jour"),
          },
        ]}
        triInitial={{ colonne: "affectes", sens: "desc" }}
        surOuvrir={(a) => setOuvertId(a.auditor_id)}
        libelleLigne={(a) => a.email}
        ligneActive={ouvertId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucun auditeur actif."
        nomExport="auditeurs"
        memoire="admin-auditeurs"
      />
      <Sheet open={ouvert !== null} onOpenChange={(o) => !o && setOuvertId(null)}>
        {ouvert ? (
          <SheetContent>
            <SheetHeader>
              <SheetTitle>{ouvert.email}</SheetTitle>
              <div className="flex gap-1.5">
                <Badge variant="info">Auditeur</Badge>
                {ouvert.overdue_reports > 0 ? (
                  <Badge variant="warning">{ouvert.overdue_reports} en retard</Badge>
                ) : (
                  <Badge variant="success">À jour</Badge>
                )}
              </div>
            </SheetHeader>
            <SheetBody>
              <SheetSection titre="Charge">
                <SheetFields
                  champs={[
                    { libelle: "Dossiers affectés", valeur: nombre(ouvert.assigned_reports) },
                    { libelle: "Dont en retard", valeur: nombre(ouvert.overdue_reports) },
                    { libelle: "Avis rendus (total)", valeur: nombre(ouvert.opinions_submitted) },
                  ]}
                />
              </SheetSection>
            </SheetBody>
            <SheetFooter>
              <Button asChild size="sm" variant="outline">
                <Link to={`/admin/journal-audit?concerne=${ouvert.auditor_id}`}>
                  Journal d’audit de ce compte
                </Link>
              </Button>
            </SheetFooter>
          </SheetContent>
        ) : null}
      </Sheet>
    </div>
  );
}
