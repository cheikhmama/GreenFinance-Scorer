import { useSearchParams } from "react-router-dom";
import { formatScore } from "@/shared/format/etatPosition";
import { Card, CardContent } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { useCompareCompaniesForResearcher } from "../api";

export function ComparisonPage() {
  const [searchParams] = useSearchParams();
  const entrepriseIds = (searchParams.get("ids") ?? "").split(",").filter(Boolean);
  const { data: entreprises, isLoading, isError } = useCompareCompaniesForResearcher(entrepriseIds);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Chercheur"
        title="Comparaison"
        description="Score ESG et émissions Scope 1/2/3, côte à côte — base d'une analyse."
      />

      {entrepriseIds.length < 2 ? (
        <p className="text-brand-grey">
          Sélectionne au moins deux entreprises depuis « Données » pour les comparer.
        </p>
      ) : null}
      {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
      {isError ? <p className="text-destructive">Impossible de charger la comparaison.</p> : null}

      {entreprises && entreprises.length >= 2 ? (
        <Card>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-brand-grey">
                  <th className="py-2 pr-4 font-medium">Critère</th>
                  {entreprises.map((entreprise) => (
                    <th key={entreprise.id} className="py-2 pr-4 font-medium text-brand-blue">
                      {entreprise.nom}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <Ligne titre="Secteur" entreprises={entreprises} render={(e) => e.secteur} />
                <Ligne titre="Pays" entreprises={entreprises} render={(e) => e.pays} />
                <Ligne
                  titre="Score global"
                  entreprises={entreprises}
                  render={(e) => formatScore(e.score.valeur_globale)}
                />
                <Ligne
                  titre="Environnement (E)"
                  entreprises={entreprises}
                  render={(e) => formatScore(e.score.score_environnement)}
                />
                <Ligne
                  titre="Social (S)"
                  entreprises={entreprises}
                  render={(e) => formatScore(e.score.score_social)}
                />
                <Ligne
                  titre="Gouvernance (G)"
                  entreprises={entreprises}
                  render={(e) => formatScore(e.score.score_gouvernance)}
                />
                <Ligne
                  titre="Scope 1 (tCO2e)"
                  entreprises={entreprises}
                  render={(e) => e.carbone.scope_1?.toLocaleString("fr-FR") ?? "—"}
                />
                <Ligne
                  titre="Scope 2, market-based (tCO2e)"
                  entreprises={entreprises}
                  render={(e) => e.carbone.scope_2_market_based?.toLocaleString("fr-FR") ?? "—"}
                />
                <Ligne
                  titre="Scope 2, location-based (tCO2e)"
                  entreprises={entreprises}
                  render={(e) => e.carbone.scope_2_location_based?.toLocaleString("fr-FR") ?? "—"}
                />
                <Ligne
                  titre="Scope 3 (tCO2e)"
                  entreprises={entreprises}
                  render={(e) => e.carbone.scope_3?.toLocaleString("fr-FR") ?? "—"}
                />
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function Ligne<T>({
  titre,
  entreprises,
  render,
}: {
  titre: string;
  entreprises: T[];
  render: (entreprise: T) => string;
}) {
  return (
    <tr className="border-b last:border-0">
      <td className="py-2 pr-4 font-medium text-brand-grey">{titre}</td>
      {entreprises.map((entreprise, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: lignes stables, une seule mise à jour par rendu
        <td key={index} className="py-2 pr-4">
          {render(entreprise)}
        </td>
      ))}
    </tr>
  );
}
