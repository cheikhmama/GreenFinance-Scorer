import { FileText } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import type { ReportStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { Select } from "@/shared/ui/select";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { useAllReports } from "../api";

const STATUTS: ReportStatus[] = [
  "EXTRACTING",
  "EXTRACTION_FAILED",
  "AWAITING_ASSIGNMENT",
  "IN_AUDIT",
  "PENDING_DECISION",
  "VALIDATED",
  "REJECTED",
  "REVISION_REQUESTED",
];

/** Vue de suivi transverse de TOUS les rapports, tous statuts confondus — contrairement aux
 * sections ci-dessus (chacune scopée à une étape précise du workflow), sert un besoin de
 * consultation globale (ex. "voir tous les rapports validés"), pas un point de traitement.
 * Destination des cartes "Rapports soumis / validés / rejetés" du tableau de bord Admin — le
 * filtre initial vient de ?statut= dans l'URL, pour que ces cartes déposent directement sur le
 * bon filtre plutôt que sur une liste non filtrée à re-trier manuellement. */
export function AllReportsSection() {
  const [searchParams, setSearchParams] = useSearchParams();
  const statut = (searchParams.get("statut") as ReportStatus | null) ?? "";
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useAllReports(statut || undefined);

  function handleStatutChange(valeur: ReportStatus | "") {
    setSearchParams(
      (params) => {
        if (valeur) {
          params.set("statut", valeur);
        } else {
          params.delete("statut");
        }
        return params;
      },
      { replace: true },
    );
  }

  const rapports = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <CardTitle>Tous les rapports</CardTitle>
        <Select
          value={statut}
          onChange={(event) => handleStatutChange(event.target.value as ReportStatus | "")}
          className="w-56"
        >
          <option value="">Tous les statuts</option>
          {STATUTS.map((valeur) => (
            <option key={valeur} value={valeur}>
              {libelleStatutRapport(valeur)}
            </option>
          ))}
        </Select>
      </CardHeader>
      <CardContent>
        {isLoading ? <CardListSkeleton count={3} /> : null}
        {isError ? <p className="text-destructive">Impossible de charger la liste.</p> : null}
        {!isLoading && !isError && rapports.length === 0 ? (
          <EmptyState icon={FileText} message="Aucun rapport pour ce filtre." />
        ) : null}
        {rapports.length > 0 ? (
          <ul className="divide-y">
            {rapports.map((rapport) => (
              <li key={rapport.id} className="flex items-center justify-between gap-4 py-3">
                <div className="flex items-center gap-2">
                  <Badge variant={variantStatutRapport(rapport.status)}>
                    {libelleStatutRapport(rapport.status)}
                  </Badge>
                  <span className="text-brand-blue">
                    {rapport.type} — {rapport.fiscal_year ?? "année inconnue"}
                  </span>
                </div>
                <Button asChild size="sm" variant="outline">
                  <Link to={`/admin/rapports/${rapport.id}`}>Voir</Link>
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
        {rapports.length > 0 && hasNextPage ? (
          <div className="mt-3">
            <Button
              variant="outline"
              size="sm"
              disabled={isFetchingNextPage}
              onClick={() => fetchNextPage()}
            >
              {isFetchingNextPage ? "Chargement..." : "Voir plus"}
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
