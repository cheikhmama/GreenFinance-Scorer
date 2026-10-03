import { Link } from "react-router-dom";
import type { TrancheScorePublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { usePerformanceESG } from "../api";
import { uneDecimale } from "@/shared/format/etatPosition";

const CARTES = [
  {
    cle: "average_global_score" as const,
    title: "Score ESG global moyen",
    definition: "Moyenne pondérée E/S/G, un score admissible par entreprise (rapport validé).",
    tone: "text-brand-blue",
  },
  {
    cle: "average_environmental_score" as const,
    title: "E — Environnement",
    definition: "Intensité carbone normalisée (Scope 1/2/3), poids 50% du score global.",
    tone: "text-emerald-700 dark:text-emerald-400",
  },
  {
    cle: "average_social_score" as const,
    title: "S — Social",
    definition: "Mixité en management, sécurité au travail — poids 25% du score global.",
    tone: "text-sky-700 dark:text-sky-400",
  },
  {
    cle: "average_governance_score" as const,
    title: "G — Gouvernance",
    definition: "Mixité au conseil d'administration — poids 25% du score global.",
    tone: "text-violet-700 dark:text-violet-400",
  },
];

/** Performance ESG agrégée — score admissible par entreprise (dernier rapport VALIDE, sous la
 * méthodologie de référence, voir app/admin/apercu.py::calculer_performance_esg), jamais une
 * moyenne fabriquée sur des entreprises sans score. Chaque carte reste lisible même à 0
 * entreprise couverte : "—" plutôt qu'un 0 qui se lirait comme le pire score possible. */
export function EsgPerformanceSection() {
  const { data, isLoading, isError } = usePerformanceESG();

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {CARTES.map((carte) => (
          <Skeleton key={carte.cle} className="h-32 w-full rounded-xl" />
        ))}
      </div>
    );
  }
  if (isError || !data) {
    return <p className="text-destructive">Impossible de charger la performance ESG.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {CARTES.map((carte) => {
          const valeur = data[carte.cle];
          return (
            <Link
              key={carte.cle}
              to="/admin/entreprises?onglet=scores"
              className="block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-green focus-visible:ring-offset-2"
            >
              <Card className="gap-2 py-5 shadow-none transition-all duration-200 ease-out hover:-translate-y-0.5 hover:border-brand-green/70 hover:shadow-md">
                <CardContent className="px-5">
                  <p className="text-sm font-medium text-muted-foreground">{carte.title}</p>
                  <p className={`mt-2 text-3xl font-semibold tabular-nums ${carte.tone}`}>
                    {valeur !== null ? uneDecimale(valeur) : "—"}
                    <span className="ml-1 text-base font-normal text-muted-foreground">/100</span>
                  </p>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">{carte.definition}</p>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>

      <Card className="shadow-none">
        <CardHeader>
          <CardTitle className="text-base text-brand-blue">Couverture et distribution</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-brand-grey">
            <span className="font-semibold text-brand-blue tabular-nums">
              {data.companies_with_score}
            </span>{" "}
            entreprise{data.companies_with_score > 1 ? "s" : ""} sur{" "}
            <span className="font-semibold text-brand-blue tabular-nums">
              {data.companies_in_scope}
            </span>{" "}
            publiée{data.companies_in_scope > 1 ? "s" : ""} disposent d'un score exploitable.
          </p>
          <DistributionBars distribution={data.distribution} />
        </CardContent>
      </Card>
    </div>
  );
}

function DistributionBars({ distribution }: { distribution: TrancheScorePublic[] }) {
  const total = distribution.reduce((somme, tranche) => somme + tranche.company_count, 0);

  if (total === 0) {
    return (
      <p className="text-sm text-brand-grey">
        Aucune entreprise avec un score exploitable pour l'instant.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {distribution.map((tranche) => (
        <div
          key={`${tranche.lower_bound}-${tranche.upper_bound}`}
          className="flex items-center gap-3"
        >
          <span className="w-16 shrink-0 text-xs text-brand-grey">
            {tranche.lower_bound}–{tranche.upper_bound}
          </span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-brand-green transition-all"
              style={{ width: `${(tranche.company_count / total) * 100}%` }}
            />
          </div>
          <span className="w-6 shrink-0 text-right text-xs tabular-nums text-brand-blue">
            {tranche.company_count}
          </span>
        </div>
      ))}
    </div>
  );
}
