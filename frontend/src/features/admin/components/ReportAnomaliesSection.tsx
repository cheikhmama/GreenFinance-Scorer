import { CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { libelleCauseExtraction } from "@/shared/format/causeExtraction";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import {
  useFailedExtractionReports,
  useOrphanReportsInValidation,
  useRetryExtraction,
  useStuckExtractionReports,
} from "../api";

function BoutonRelancer({ rapportId }: { rapportId: string }) {
  const retry = useRetryExtraction();
  const [erreur, setErreur] = useState<string | null>(null);

  if (retry.isSuccess) {
    return <span className="text-sm text-brand-green">Relance en cours…</span>;
  }
  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        size="sm"
        variant="outline"
        disabled={retry.isPending}
        onClick={() => {
          setErreur(null);
          retry.mutate(rapportId, { onError: (e) => setErreur(e.message) });
        }}
      >
        {retry.isPending ? "Relance..." : "Relancer"}
      </Button>
      {erreur ? <p className="text-xs text-destructive">{erreur}</p> : null}
    </div>
  );
}

/** États incohérents/orphelins qu'aucune file normale ne surface (BUG-017/018) — un rapport en
 * échec d'extraction ou un rapport EN_VALIDATION sans avis restent invisibles de la file
 * d'affectation/de décision normale, jamais silencieusement ignorés pour autant. Affichée dans
 * l'onglet "Alertes" (AdminReportsPage), avec un état vide explicite plutôt que de disparaître —
 * l'onglet lui-même reste sélectionnable même sans rien à traiter, pour confirmer l'absence
 * d'anomalie plutôt que de laisser un doute. */
export function ReportAnomaliesSection() {
  const { data: echecsExtraction } = useFailedExtractionReports();
  const { data: bloques } = useStuckExtractionReports();
  const { data: orphelins } = useOrphanReportsInValidation();

  const aucuneAnomalie =
    echecsExtraction !== undefined &&
    bloques !== undefined &&
    orphelins !== undefined &&
    echecsExtraction.length === 0 &&
    bloques.length === 0 &&
    orphelins.length === 0;

  return (
    <Card className="border-amber-300">
      <CardHeader>
        <CardTitle className="text-base text-amber-700">Anomalies à traiter</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {echecsExtraction === undefined || bloques === undefined || orphelins === undefined ? (
          <CardListSkeleton count={2} />
        ) : null}
        {aucuneAnomalie ? (
          <EmptyState icon={CheckCircle2} message="Aucune anomalie détectée." />
        ) : null}
        {echecsExtraction && echecsExtraction.length > 0 ? (
          <div>
            <p className="mb-2 text-sm font-medium text-brand-blue">
              Extractions en échec ({echecsExtraction.length})
            </p>
            <ul className="divide-y">
              {echecsExtraction.map((rapport) => (
                <li key={rapport.id} className="flex items-center justify-between gap-4 py-2">
                  <div>
                    <p className="text-sm font-medium text-brand-blue">
                      {rapport.type} — {rapport.annee_reporting ?? "année inconnue"}
                    </p>
                    <p className="text-sm text-brand-grey">
                      {libelleCauseExtraction(rapport.extraction_erreur)}
                      {rapport.tentatives_extraction > 0
                        ? ` — ${rapport.tentatives_extraction} tentative(s)`
                        : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <BoutonRelancer rapportId={rapport.id} />
                    <Button asChild size="sm" variant="outline">
                      <Link to={`/admin/rapports/${rapport.id}`}>Voir</Link>
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {bloques && bloques.length > 0 ? (
          <div>
            <p className="mb-2 text-sm font-medium text-brand-blue">
              Extractions probablement interrompues ({bloques.length})
            </p>
            <ul className="divide-y">
              {bloques.map((rapport) => (
                <li key={rapport.id} className="flex items-center justify-between gap-4 py-2">
                  <div>
                    <p className="text-sm font-medium text-brand-blue">
                      {rapport.type} — {rapport.annee_reporting ?? "année inconnue"}
                    </p>
                    <p className="text-sm text-brand-grey">
                      Aucune fin ni erreur détectée depuis un délai anormal — le traitement a
                      probablement été interrompu.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <BoutonRelancer rapportId={rapport.id} />
                    <Button asChild size="sm" variant="outline">
                      <Link to={`/admin/rapports/${rapport.id}`}>Voir</Link>
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {orphelins && orphelins.length > 0 ? (
          <div>
            <p className="mb-2 text-sm font-medium text-brand-blue">
              En attente de décision, sans avis d'audit ({orphelins.length})
            </p>
            <ul className="divide-y">
              {orphelins.map((rapport) => (
                <li key={rapport.id} className="flex items-center justify-between gap-4 py-2">
                  <p className="text-sm font-medium text-brand-blue">
                    {rapport.type} — {rapport.annee_reporting ?? "année inconnue"}
                  </p>
                  <Button asChild size="sm" variant="outline">
                    <Link to={`/admin/rapports/${rapport.id}`}>Voir</Link>
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
