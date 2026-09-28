import { useParams } from "react-router-dom";
import { CarbonSummary, ScoreSummary } from "@/shared/esg/EsgSummary";
import { CarbonTable, IndicatorsTable } from "@/shared/esg/EvidenceTables";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { useCompanyDetailForInstitution } from "../api";

/** Fiche entreprise publiée, consultée depuis le périmètre d'un projet (voir
 * ProjectDetailPage) — même détail (score, carbone, preuves) que côté Chercheur/Investisseur,
 * app/investor/entreprises.py restant l'unique source de vérité. */
export function CompanyDetailPage() {
  const { entrepriseId = "" } = useParams();
  const { data: entreprise, isLoading, isError } = useCompanyDetailForInstitution(entrepriseId);

  if (isLoading) return <p className="text-brand-grey">Chargement...</p>;
  if (isError || !entreprise) return <p className="text-destructive">Entreprise introuvable.</p>;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={`${entreprise.secteur} — ${entreprise.pays}`}
        title={entreprise.nom}
        description={entreprise.description ?? "Fiche entreprise publiée."}
      />

      <Card>
        <CardHeader>
          <CardTitle>Score ESG</CardTitle>
        </CardHeader>
        <CardContent>
          <ScoreSummary score={entreprise.score} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Émissions Scope 1/2/3</CardTitle>
        </CardHeader>
        <CardContent>
          <CarbonSummary carbone={entreprise.carbone} />
        </CardContent>
      </Card>

      <IndicatorsTable
        indicateurs={entreprise.indicateurs}
        couverture={entreprise.couverture}
        construireUrlPreuve={(preuveId) =>
          `/api/v1/institution/entreprises/${entrepriseId}/preuves/${preuveId}/fichier`
        }
      />
      <CarbonTable
        donneesCarbone={entreprise.donnees_carbone}
        construireUrlPreuve={(preuveId) =>
          `/api/v1/institution/entreprises/${entrepriseId}/preuves/${preuveId}/fichier`
        }
      />
    </div>
  );
}
