import { Link } from "react-router-dom";
import { libelleDecisionAudit } from "@/shared/format/decisionAudit";
import { Card, CardContent } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { useAuditHistory } from "../api";

export function AuditHistoryPage() {
  const { data: avis, isLoading, isError } = useAuditHistory();

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Auditeur"
        title="Historique de mes avis"
        description="Dossiers sur lesquels un avis a déjà été rendu."
      />

      <Card>
        <CardContent className="pt-6">
          {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
          {isError ? <p className="text-destructive">Impossible de charger l'historique.</p> : null}
          {!isLoading && !isError && avis?.length === 0 ? (
            <p className="text-brand-grey">Aucun avis rendu pour l'instant.</p>
          ) : null}
          {avis && avis.length > 0 ? (
            <ul className="divide-y">
              {avis.map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-4 py-3">
                  <div>
                    <p className="font-medium text-brand-blue">
                      {libelleDecisionAudit(item.decision)}
                    </p>
                    {item.commentaire ? (
                      <p className="text-sm text-brand-grey">{item.commentaire}</p>
                    ) : null}
                  </div>
                  <div className="flex flex-col items-end gap-1 text-sm text-brand-grey">
                    <span>{new Date(item.date_avis).toLocaleDateString("fr-FR")}</span>
                    <Link
                      to={`/audit/rapports/${item.rapport_id}`}
                      className="text-brand-green underline underline-offset-2"
                    >
                      Voir le dossier
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
