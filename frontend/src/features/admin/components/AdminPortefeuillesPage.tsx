import { useMemo, useState } from "react";
import type { PortefeuilleAdmin } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { formatMontant } from "@/shared/format/etatPosition";
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

/** Tous les portefeuilles non archivés, tous Investisseurs confondus (table, tâche 5.17). */
export function AdminPortefeuillesPage() {
  const { data, isLoading, isError } = useTablePortefeuilles();
  const [ouvertId, setOuvertId] = useState<string | null>(null);

  const colonnes = useMemo<ColonneTable<PortefeuilleAdmin>[]>(
    () => [
      {
        id: "nom",
        entete: "Portefeuille",
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
        id: "positions",
        entete: "Positions",
        alignement: "droite",
        valeurTri: (p) => p.position_count,
        cellule: (p) => <span className="font-mono">{p.position_count}</span>,
      },
      {
        id: "montant",
        entete: "Montant total",
        alignement: "droite",
        valeurTri: (p) => p.total_amount,
        cellule: (p) => (
          <span className="font-mono font-semibold">
            {formatMontant(p.total_amount, p.reference_currency)}
          </span>
        ),
      },
    ],
    [],
  );
  const ouvert = data?.find((p) => p.id === ouvertId) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Portefeuilles"
        description="Tous les portefeuilles non archivés, tous investisseurs confondus."
      />
      <DataTable
        libelle="Portefeuilles"
        lignes={data}
        colonnes={colonnes}
        cle={(p) => p.id}
        rechercheDans={(p) => `${p.name} ${p.investor_email}`}
        placeholderRecherche="Portefeuille, titulaire…"
        filtres={[{ id: "devise", libelle: "Devise", valeur: (p) => p.reference_currency }]}
        triInitial={{ colonne: "montant", sens: "desc" }}
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
                    {
                      libelle: "Positions",
                      valeur: <span className="font-mono">{ouvert.position_count}</span>,
                    },
                    {
                      libelle: "Montant total",
                      valeur: (
                        <span className="font-mono font-semibold">
                          {formatMontant(ouvert.total_amount, ouvert.reference_currency)}
                        </span>
                      ),
                    },
                    { libelle: "Devise de référence", valeur: ouvert.reference_currency },
                    {
                      libelle: "Créé le",
                      valeur: new Date(ouvert.created_at).toLocaleDateString("fr-FR"),
                    },
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
