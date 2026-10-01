import type {
  DonneesCarboneAgregees,
  ScoreEntreprisePublic,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { formatPourcentage, formatScore } from "@/shared/format/etatPosition";

const TEINTES_PILIER: Record<"global" | "E" | "S" | "G", string> = {
  global: "bg-brand-green",
  E: "bg-emerald-500",
  S: "bg-blue-500",
  G: "bg-violet-500",
};

/** Barre de niveau 0-100 sous chaque score — une lecture visuelle immédiate en plus du chiffre,
 * jamais l'inverse (le chiffre exact reste la source de vérité, la barre l'illustre). */
function BarreScore({ valeur, teinte }: { valeur: number | null; teinte: string }) {
  return (
    <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-muted">
      {valeur !== null ? (
        <div
          className={`h-full rounded-full ${teinte}`}
          style={{ width: `${Math.max(0, Math.min(100, valeur))}%` }}
        />
      ) : null}
    </div>
  );
}

/** Résumé du score ESG d'une entreprise publiée — partagé entre les espaces Investisseur et
 * Chercheur (même donnée, même présentation, deux consommateurs réels : voir
 * FRONTEND-ARCHITECTURE.md §2.2 sur le seuil de remontée dans shared/). */
export function ScoreSummary({ score }: { score: ScoreEntreprisePublic }) {
  return (
    <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">Score global</dt>
        <dd className="mt-0.5 font-semibold text-brand-blue">{formatScore(score.global_score)}</dd>
        <BarreScore valeur={score.global_score} teinte={TEINTES_PILIER.global} />
        {/* Un score ne se lit jamais sans sa couverture (tâche 3.1) : part pondérée des
            indicateurs de la méthodologie effectivement publiés par l'entreprise. */}
        {score.coverage_rate != null ? (
          <dd className="mt-1 text-xs text-brand-grey">
            Couverture {formatPourcentage(score.coverage_rate * 100)}
          </dd>
        ) : null}
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">E</dt>
        <dd className="mt-0.5 font-semibold text-brand-blue">
          {formatScore(score.environmental_score)}
        </dd>
        <BarreScore valeur={score.environmental_score} teinte={TEINTES_PILIER.E} />
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">S</dt>
        <dd className="mt-0.5 font-semibold text-brand-blue">{formatScore(score.social_score)}</dd>
        <BarreScore valeur={score.social_score} teinte={TEINTES_PILIER.S} />
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">G</dt>
        <dd className="mt-0.5 font-semibold text-brand-blue">
          {formatScore(score.governance_score)}
        </dd>
        <BarreScore valeur={score.governance_score} teinte={TEINTES_PILIER.G} />
      </div>
    </dl>
  );
}

function formatTonnes(valeur: number | null): string {
  return valeur === null ? "—" : `${valeur.toLocaleString("fr-FR")} tCO2e`;
}

export function CarbonSummary({ carbone }: { carbone: DonneesCarboneAgregees }) {
  return (
    <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">Scope 1</dt>
        <dd className="mt-0.5 font-medium">{formatTonnes(carbone.scope_1)}</dd>
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">Scope 2 (market)</dt>
        <dd className="mt-0.5 font-medium">{formatTonnes(carbone.scope_2_market_based)}</dd>
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">
          Scope 2 (location)
        </dt>
        <dd className="mt-0.5 font-medium">{formatTonnes(carbone.scope_2_location_based)}</dd>
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">Scope 3</dt>
        <dd className="mt-0.5 font-medium">{formatTonnes(carbone.scope_3)}</dd>
      </div>
    </dl>
  );
}
