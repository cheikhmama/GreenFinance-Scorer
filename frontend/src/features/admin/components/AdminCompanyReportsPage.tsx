import { FileText } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import {
  libelleDateRapport,
  libelleStatutRapport,
  variantStatutRapport,
} from "@/shared/format/statut";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { EmptyState } from "@/shared/ui/empty-state";
import { PageHeader } from "@/shared/ui/page-header";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { useCompanyReports } from "../api";

export function AdminCompanyReportsPage() {
  const { entrepriseId } = useParams<{ entrepriseId: string }>();
  const { data: rapports, isLoading, isError } = useCompanyReports(entrepriseId ?? "");

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Rapports de l'entreprise"
        description="Tous les rapports déposés, quel que soit leur statut."
      />
      <Link to="/admin/entreprises" className="text-sm text-brand-green underline underline-offset-2">
        ← Entreprises
      </Link>

      {isLoading ? <CardListSkeleton count={3} /> : null}
      {isError ? <p className="text-destructive">Impossible de charger les rapports.</p> : null}
      {!isLoading && !isError && rapports && rapports.length === 0 ? (
        <EmptyState icon={FileText} message="Aucun rapport déposé par cette entreprise." />
      ) : null}
      {rapports && rapports.length > 0 ? (
        <ul className="divide-y rounded-lg border">
          {rapports.map((rapport) => (
            <li key={rapport.id} className="flex items-center justify-between gap-4 p-4">
              <div>
                <p className="font-medium text-brand-blue">
                  {rapport.type} — {rapport.fiscal_year ?? "année inconnue"}
                </p>
                <p className="text-xs text-brand-grey">
                  {libelleDateRapport(rapport)} — version{" "}
                  {rapport.version}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={variantStatutRapport(rapport.status)}>
                  {libelleStatutRapport(rapport.status)}
                </Badge>
                <Button asChild size="sm" variant="outline">
                  <Link to={`/admin/rapports/${rapport.id}`}>Ouvrir</Link>
                </Button>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
