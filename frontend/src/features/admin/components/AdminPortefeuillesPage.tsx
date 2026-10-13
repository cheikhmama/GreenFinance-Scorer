import { useMemo, useState } from "react";
import type { PortefeuilleAdmin } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
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
import { useTablePortefeuilles } from "../api";

/** Tous les portefeuilles non archivés, tous Investisseurs confondus — détail derrière
 * "Portefeuilles non archivés" de l'onglet Investisseur du tableau de bord. Suivi en lecture
 * seule, aux seules colonnes non sensibles : nom, titulaire, date de création — jamais la
 * composition, le nombre de positions ni un montant, qui restent privés à son titulaire. */
function dateFr(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR");
}

export function AdminPortefeuillesPage() {
  const { data, isLoading, isError } = useTablePortefeuilles();
  const [ouvertId, setOuvertId] = useState<string | null>(null);

  const colonnes = useMemo<ColonneTable<PortefeuilleAdmin>[]>(
    () => [
      {
        id: "nom",
        entete: "Nom du portefeuille",
        masquable: false,
        valeurTri: (p) => p.name,
        cellule: (p) => <span className="font-semibold text-foreground">{p.name}</span>,
      },
      {
        id: "titulaire",
        entete: "Titulaire",
        valeurTri: (p) => p.investor_email,
        cellule: (p) => <span className="font-mono text-[12.5px]">{p.investor_email}</span>,
      },
      {
        id: "creation",
        entete: "Date de création",
        valeurTri: (p) => p.created_at,
        valeurExport: (p) => dateFr(p.created_at),
        cellule: (p) => <span className="font-mono">{dateFr(p.created_at)}</span>,
      },
    ],
    [],
  );
  const ouvert = data?.find((p) => p.id === ouvertId) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader title="Portefeuilles" />
      <DataTable
        libelle="Portefeuilles"
        lignes={data}
        colonnes={colonnes}
        cle={(p) => p.id}
        rechercheDans={(p) => `${p.name} ${p.investor_email}`}
        placeholderRecherche="Portefeuille, titulaire…"
        triInitial={{ colonne: "creation", sens: "desc" }}
        surOuvrir={(p) => setOuvertId(p.id)}
        libelleLigne={(p) => p.name}
        ligneActive={ouvertId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucun portefeuille."
        nomExport="portefeuilles"
        memoire="admin-portefeuilles"
      />
      <Sheet open={ouvert !== null} onOpenChange={(o) => !o && setOuvertId(null)}>
        {ouvert ? (
          <SheetContent>
            <SheetHeader>
              <SheetTitle>{ouvert.name}</SheetTitle>
              <SheetDescription>{ouvert.investor_email}</SheetDescription>
            </SheetHeader>
            <SheetBody>
              <SheetSection titre="Portefeuille">
                <SheetFields
                  champs={[
                    { libelle: "Titulaire", valeur: ouvert.investor_email },
                    { libelle: "Date de création", valeur: dateFr(ouvert.created_at) },
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
