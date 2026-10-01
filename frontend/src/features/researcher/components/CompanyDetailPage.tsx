import { useParams } from "react-router-dom";
import { CarbonSummary, ScoreSummary } from "@/shared/esg/EsgSummary";
import { CarbonTable, IndicatorsTable } from "@/shared/esg/EvidenceTables";
import { ScoreWaterfall } from "@/shared/esg/ScoreWaterfall";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { useCompanyDetailForResearcher } from "../api";

export function CompanyDetailPage() {
  const { entrepriseId = "" } = useParams();
  const { data: entreprise, isLoading, isError } = useCompanyDetailForResearcher(entrepriseId);

  if (isLoading) return <p className="text-brand-grey">Chargement...</p>;
  if (isError || !entreprise) return <p className="text-destructive">Entreprise introuvable.</p>;

  return (
    <div className="space-y-6">
      <PageHeader
        title={entreprise.name}
        description={`${entreprise.sector} — ${entreprise.country}. ${entreprise.description ?? "Fiche entreprise publiée."}`}
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
          <CardTitle>Émissions Scope 1/2/3</CardTitle>
        </CardHeader>
        <CardContent>
          <CarbonSummary carbone={entreprise.carbon} />
        </CardContent>
      </Card>

      <IndicatorsTable
        indicateurs={entreprise.metrics}
        couverture={entreprise.coverage}
        construireUrlPreuve={(preuveId) =>
          `/api/v1/researcher/entreprises/${entrepriseId}/preuves/${preuveId}/fichier`
        }
      />
      <CarbonTable
        donneesCarbone={entreprise.carbon_data}
        construireUrlPreuve={(preuveId) =>
          `/api/v1/researcher/entreprises/${entrepriseId}/preuves/${preuveId}/fichier`
        }
      />
    </div>
  );
}
