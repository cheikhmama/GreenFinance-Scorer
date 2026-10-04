import { useParams } from "react-router-dom";
import { CarbonSummary, ScoreSummary } from "@/shared/esg/EsgSummary";
import { CarbonTable, IndicatorsTable } from "@/shared/esg/EvidenceTables";
import { ScoreWaterfall } from "@/shared/esg/ScoreWaterfall";
import { libellePays } from "@/shared/format/pays";
import { BackLink } from "@/shared/ui/back-link";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { PageSkeleton } from "@/shared/ui/skeleton";
import { useCompanyDetailForInstitution } from "../api";

/** Fiche entreprise publiée, consultée depuis le périmètre d'un projet (voir
 * ProjectDetailPage) — même détail (score, carbone, preuves) que côté Chercheur/Investisseur,
 * app/investor/entreprises.py restant l'unique source de vérité. */
export function CompanyDetailPage() {
  const { entrepriseId = "" } = useParams();
  const { data: entreprise, isLoading, isError } = useCompanyDetailForInstitution(entrepriseId);

  if (isLoading) return <PageSkeleton />;
  if (isError || !entreprise) return <p className="text-destructive">Entreprise introuvable.</p>;

  return (
    <div className="space-y-6">
      <BackLink to="/institution/entreprises">Entreprises</BackLink>
      <PageHeader
        title={entreprise.name}
        description={`${entreprise.sector} — ${libellePays(entreprise.country)}. ${entreprise.description ?? "Fiche entreprise publiée."}`}
      />

      <Card>
        <CardHeader>
          <CardTitle>Score ESG</CardTitle>
        </CardHeader>
        <CardContent>
          <ScoreSummary score={entreprise.score} />
        </CardContent>
      </Card>

      {entreprise.report_id && entreprise.score.global_score !== null ? (
        <Card>
          <CardHeader>
            <CardTitle>D’où vient ce score ?</CardTitle>
          </CardHeader>
          <CardContent>
            <ScoreWaterfall rapportId={entreprise.report_id} />
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Émissions (Scopes 1, 2 et 3)</CardTitle>
        </CardHeader>
        <CardContent>
          <CarbonSummary carbone={entreprise.carbon} />
        </CardContent>
      </Card>

      <IndicatorsTable
        indicateurs={entreprise.metrics}
        couverture={entreprise.coverage}
        construireUrlPreuve={(preuveId) =>
          `/api/v1/institution/entreprises/${entrepriseId}/preuves/${preuveId}/fichier`
        }
      />
      <CarbonTable
        donneesCarbone={entreprise.carbon_data}
        construireUrlPreuve={(preuveId) =>
          `/api/v1/institution/entreprises/${entrepriseId}/preuves/${preuveId}/fichier`
        }
      />
    </div>
  );
}
