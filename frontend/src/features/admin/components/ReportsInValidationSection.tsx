import { Link } from "react-router-dom";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { useReportsInValidation } from "../api";

/** File de décision (Phase 4 §4.4) — un avis d'audit a déjà été rendu ; la décision elle-même
 * (valider/rejeter/demander correction) se prend depuis le détail du rapport. */
export function ReportsInValidationSection() {
  const { data: rapports, isLoading, isError } = useReportsInValidation();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Rapports en attente de décision</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
        {isError ? <p className="text-destructive">Impossible de charger la file.</p> : null}
        {!isLoading && !isError && rapports?.length === 0 ? (
          <p className="text-brand-grey">Aucun rapport en attente de décision.</p>
        ) : null}
        {rapports && rapports.length > 0 ? (
          <ul className="divide-y">
            {rapports.map((rapport) => (
              <li key={rapport.id} className="flex items-center justify-between gap-4 py-3">
                <div className="flex items-center gap-2">
                  <Badge variant={variantStatutRapport(rapport.statut)}>
                    {libelleStatutRapport(rapport.statut)}
                  </Badge>
                  <span className="text-brand-blue">
                    {rapport.type} — {rapport.annee_reporting ?? "année inconnue"}
                  </span>
                </div>
                <Link
                  to={`/admin/rapports/${rapport.id}`}
                  className="text-brand-green underline underline-offset-2"
                >
                  Décider
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}
