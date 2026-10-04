import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { uneDecimale } from "@/shared/format/etatPosition";
import { libelleTypeRapport } from "@/shared/format/typeRapport";
import { BackLink } from "@/shared/ui/back-link";
import { type ColonneTable, DataTable } from "@/shared/ui/data-table";
import { PageHeader } from "@/shared/ui/page-header";
import { useCompanyDetail, useCompanyReports } from "../api";
import { type Ligne, RapportTiroir } from "./RapportsTable";

/** Tous les rapports d'une entreprise (table, tâche 5.17) : exercice, type, version et score ;
 * statut, dates et actions dans le tiroir partagé avec la page Rapports. */
export function AdminCompanyReportsPage() {
  const { entrepriseId } = useParams<{ entrepriseId: string }>();
  const { data: entreprise } = useCompanyDetail(entrepriseId ?? "");
  const { data: rapports, isLoading, isError } = useCompanyReports(entrepriseId ?? "");
  const [ouvertId, setOuvertId] = useState<string | null>(null);

  const lignes = useMemo<Ligne[] | undefined>(
    () => rapports?.map((r) => ({ ...r, company_name: entreprise?.name ?? "" })),
    [rapports, entreprise?.name],
  );

  const colonnes = useMemo<ColonneTable<Ligne>[]>(
    () => [
      {
        id: "exercice",
        entete: "Exercice",
        masquable: false,
        valeurTri: (r) => r.fiscal_year,
        cellule: (r) => <span className="font-mono font-semibold">{r.fiscal_year ?? "—"}</span>,
      },
      {
        id: "type",
        entete: "Type de rapport",
        valeurTri: (r) => libelleTypeRapport(r.type),
        cellule: (r) => libelleTypeRapport(r.type),
      },
      {
        id: "version",
        entete: "Version",
        alignement: "droite",
        valeurTri: (r) => r.version,
        cellule: (r) => <span className="font-mono">{r.version}</span>,
      },
      {
        id: "score",
        entete: "Score ESG",
        alignement: "droite",
        valeurTri: (r) => r.official_global_score ?? null,
        cellule: (r) => (
          <span className="font-mono font-semibold">
            {r.official_global_score != null ? uneDecimale(r.official_global_score) : "—"}
          </span>
        ),
      },
    ],
    [],
  );
  const ouvert = lignes?.find((r) => r.id === ouvertId) ?? null;

  return (
    <div className="space-y-6">
      <BackLink to={entrepriseId ? `/admin/entreprises/${entrepriseId}` : "/admin/entreprises"}>
        {entreprise?.name ?? "Entreprise"}
      </BackLink>
      <PageHeader
        title="Rapports de l'entreprise"
        description="Tous les rapports déposés, quel que soit leur statut."
      />
      <DataTable
        libelle={`Rapports de ${entreprise?.name ?? "l’entreprise"}`}
        lignes={lignes}
        colonnes={colonnes}
        cle={(r) => r.id}
        rechercheDans={(r) => `${libelleTypeRapport(r.type)} ${r.fiscal_year ?? ""}`}
        placeholderRecherche="Type, exercice…"
        filtres={[{ id: "type", libelle: "Type", valeur: (r) => libelleTypeRapport(r.type) }]}
        triInitial={{ colonne: "exercice", sens: "desc" }}
        surOuvrir={(r) => setOuvertId(r.id)}
        libelleLigne={(r) => `${libelleTypeRapport(r.type)} ${r.fiscal_year ?? ""}`}
        ligneActive={ouvertId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucun rapport déposé par cette entreprise."
        nomExport="rapports-entreprise"
        memoire="admin-rapports-entreprise"
      />
      <RapportTiroir rapport={ouvert} surFermer={() => setOuvertId(null)} />
    </div>
  );
}
