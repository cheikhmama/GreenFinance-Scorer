import type { CarbonExclusionReason } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { formatPourcentage } from "@/shared/format/etatPosition";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { usePortfolioCarbon } from "../api";

const MOTIFS: Record<CarbonExclusionReason, string> = {
  UNMATCHED: "ligne importée non rapprochée",
  NO_VALIDATED_REPORT: "aucun rapport validé",
  MISSING_EMISSIONS: "Scope 1 ou Scope 2 non publié",
  MISSING_EVIC: "EVIC non renseignée",
};

function tonnes(valeur: number | null): string {
  return valeur === null
    ? "—"
    : `${valeur.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} tCO₂e`;
}

function nombre(valeur: number | null, unite: string): string {
  return valeur === null
    ? "—"
    : `${valeur.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} ${unite}`;
}

/** Empreinte carbone PCAF des positions actives (tâche 2.3). Chaque indicateur affiche sa propre
 * couverture ; une donnée manquante n'est jamais comptée comme zéro, les lignes exclues sont
 * listées avec leur motif. */
export function PortfolioCarbonCard({ portefeuilleId }: { portefeuilleId: string }) {
  const { data, isLoading, isError } = usePortfolioCarbon(portefeuilleId);

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (isError || !data) {
    return <p className="text-destructive">Impossible de calculer l’empreinte carbone.</p>;
  }

  const devise = data.currency;
  const exclusions = new Map<CarbonExclusionReason, number>();
  for (const position of data.positions) {
    if (position.excluded_reason) {
      exclusions.set(position.excluded_reason, (exclusions.get(position.excluded_reason) ?? 0) + 1);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Empreinte carbone (PCAF)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {data.positions.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucune position active : l’empreinte porte sur les encours détenus aujourd’hui.
          </p>
        ) : (
          <>
            <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Indicateur
                label="Émissions financées, Scopes 1+2"
                valeur={tonnes(data.financed_emissions_scope_1_2)}
                couverture={data.coverage_scope_1_2}
              />
              <Indicateur
                label="Émissions financées, Scope 3 (à part)"
                valeur={tonnes(data.financed_emissions_scope_3)}
                couverture={data.coverage_scope_3}
              />
              <Indicateur
                label="Empreinte carbone, Scopes 1+2"
                valeur={nombre(data.carbon_footprint_scope_1_2, `tCO₂e / M ${devise} investi`)}
                couverture={data.coverage_scope_1_2}
              />
              <Indicateur
                label="WACI, Scopes 1+2"
                valeur={nombre(data.waci_scope_1_2, `tCO₂e / M ${devise} de CA`)}
                couverture={data.coverage_waci}
              />
              <Indicateur
                label="Qualité des données PCAF"
                valeur={
                  data.data_quality_scope_1_2 === null
                    ? "—"
                    : `${data.data_quality_scope_1_2.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} / 5`
                }
                aide="1 = données vérifiées, 5 = estimations sectorielles"
              />
            </dl>
            {exclusions.size > 0 ? (
              <div className="text-sm text-muted-foreground">
                <p>Positions hors du calcul des Scopes 1+2 :</p>
                <ul className="mt-1 list-disc pl-5">
                  {[...exclusions].map(([motif, nombreLignes]) => (
                    <li key={motif}>
                      {nombreLignes} × {MOTIFS[motif]}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Indicateur({
  label,
  valeur,
  couverture,
  aide,
}: {
  label: string;
  valeur: string;
  couverture?: number;
  aide?: string;
}) {
  return (
    <div className="rounded-lg border p-4">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-lg font-semibold text-foreground">{valeur}</dd>
      <dd className="text-xs text-muted-foreground">
        {couverture !== undefined ? `Couverture ${formatPourcentage(couverture * 100)}` : aide}
      </dd>
    </div>
  );
}
