import { FileCheck2 } from "lucide-react";
import { Link } from "react-router-dom";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { CardListSkeleton } from "@/shared/ui/skeleton";
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
        {isLoading ? <CardListSkeleton count={2} /> : null}
        {isError ? <p className="text-destructive">Impossible de charger la file.</p> : null}
        {!isLoading && !isError && rapports?.length === 0 ? (
          <EmptyState icon={FileCheck2} message="Aucun rapport en attente de décision." />
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
                <Button asChild size="sm">
                  <Link to={`/admin/rapports/${rapport.id}`}>Décider</Link>
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}
