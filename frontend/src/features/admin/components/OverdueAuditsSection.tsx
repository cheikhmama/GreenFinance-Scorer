import { CheckCircle2 } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { useOverdueReports } from "../api";
import { titreDeclaration } from "@/shared/format/typeRapport";

/** Rapports affectés à un auditeur depuis plus longtemps que le délai attendu, sans décision
 * rendue — voir app/admin/review_queue.py::lister_rapports_en_retard. Affichée dans l'onglet
 * "Alertes" (AdminReportsPage), avec un état vide explicite plutôt que de disparaître. */
export function OverdueAuditsSection() {
  const { data: rapports } = useOverdueReports();

  return (
    <Card className="border-amber-300">
      <CardHeader>
        <CardTitle className="text-base text-amber-700">Audits en retard</CardTitle>
      </CardHeader>
      <CardContent>
        {rapports === undefined ? <CardListSkeleton count={2} /> : null}
        {rapports && rapports.length === 0 ? (
          <EmptyState icon={CheckCircle2} message="Aucun audit en retard." />
        ) : null}
        {rapports && rapports.length > 0 ? (
          <ul className="divide-y">
            {rapports.map((rapport) => (
              <li key={rapport.id} className="flex items-center justify-between gap-4 py-2">
                <p className="text-sm font-medium text-brand-blue">
                  {rapport.company_name ? `${rapport.company_name} · ` : ""}
{titreDeclaration(rapport)}
                </p>
                <Button asChild size="sm" variant="outline">
                  <Link to={`/admin/rapports/${rapport.id}`}>Voir</Link>
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}
