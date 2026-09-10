import { Link, useParams } from "react-router-dom";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import { Badge } from "@/shared/ui/badge";
import { PageHeader } from "@/shared/ui/page-header";
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

      {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
      {isError ? <p className="text-destructive">Impossible de charger les rapports.</p> : null}
      {!isLoading && !isError && rapports && rapports.length === 0 ? (
        <p className="text-brand-grey">Aucun rapport déposé par cette entreprise.</p>
      ) : null}
      {rapports && rapports.length > 0 ? (
        <ul className="divide-y rounded-lg border">
          {rapports.map((rapport) => (
            <li key={rapport.id} className="flex items-center justify-between gap-4 p-4">
              <div>
                <p className="font-medium text-brand-blue">
                  {rapport.type} — {rapport.annee_reporting ?? "année inconnue"}
                </p>
                <p className="text-xs text-brand-grey">
                  Déposé le {new Date(rapport.date_depot).toLocaleDateString("fr-FR")} — version{" "}
                  {rapport.version}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={variantStatutRapport(rapport.statut)}>
                  {libelleStatutRapport(rapport.statut)}
                </Badge>
                <Link
                  to={`/admin/rapports/${rapport.id}`}
                  className="text-sm text-brand-green underline underline-offset-2"
                >
                  Ouvrir
                </Link>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
