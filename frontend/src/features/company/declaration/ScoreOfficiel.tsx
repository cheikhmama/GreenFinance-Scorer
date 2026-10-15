import type { ScoreESGPublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";

export function arrondi(valeur: number) {
  return valeur.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
}

/** Score officiel d'une déclaration validée : global, puis un score par pilier. */
export function ScoreOfficiel({ score }: { score: ScoreESGPublic }) {
  const piliers = [
    ["Environnement", score.environmental_score],
    ["Social", score.social_score],
    ["Gouvernance", score.governance_score],
  ] as const;
  return (
    <Card role="region" aria-label="Score officiel">
      <CardHeader>
        <CardTitle className="text-base">Score officiel</CardTitle>
        <CardDescription>
          Calculé après validation de l’auditeur
          {score.coverage_rate != null
            ? ` · couverture ${Math.round(score.coverage_rate * 100)} %`
            : ""}{" "}
          · configuration v{score.config_version}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 sm:grid-cols-[auto_1fr] sm:items-center">
        <p className="text-4xl font-semibold tabular-nums text-foreground">
          {arrondi(score.global_score)}
          <span className="text-base font-normal text-muted-foreground">/100</span>
        </p>
        <ul className="space-y-3 sm:border-l sm:pl-6">
          {piliers.map(([libelle, valeur]) => (
            <li key={libelle} className="grid grid-cols-[7rem_1fr_3rem] items-center gap-3">
              <span className="text-sm text-muted-foreground">{libelle}</span>
              <span
                className="h-2 overflow-hidden rounded-full bg-muted"
                role="progressbar"
                aria-label={libelle}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={valeur ?? undefined}
              >
                <span
                  className="block h-full rounded-full bg-primary"
                  style={{ width: `${valeur ?? 0}%` }}
                />
              </span>
              <span className="text-right text-sm font-medium tabular-nums text-foreground">
                {valeur != null ? arrondi(valeur) : "—"}
              </span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
