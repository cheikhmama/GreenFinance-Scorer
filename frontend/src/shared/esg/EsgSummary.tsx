import type {
  DonneesCarboneAgregees,
  ScoreEntreprisePublic,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { formatScore } from "@/shared/format/etatPosition";

/** Résumé du score ESG d'une entreprise publiée — partagé entre les espaces Investisseur et
 * Chercheur (même donnée, même présentation, deux consommateurs réels : voir
 * FRONTEND-ARCHITECTURE.md §2.2 sur le seuil de remontée dans shared/). */
export function ScoreSummary({ score }: { score: ScoreEntreprisePublic }) {
  return (
    <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">Score global</dt>
        <dd className="mt-0.5 font-semibold text-brand-blue">{formatScore(score.valeur_globale)}</dd>
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">E</dt>
        <dd className="mt-0.5 font-semibold text-brand-blue">{formatScore(score.score_environnement)}</dd>
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">S</dt>
        <dd className="mt-0.5 font-semibold text-brand-blue">{formatScore(score.score_social)}</dd>
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">G</dt>
        <dd className="mt-0.5 font-semibold text-brand-blue">{formatScore(score.score_gouvernance)}</dd>
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
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">Scope 2 (location)</dt>
        <dd className="mt-0.5 font-medium">{formatTonnes(carbone.scope_2_location_based)}</dd>
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">Scope 3</dt>
        <dd className="mt-0.5 font-medium">{formatTonnes(carbone.scope_3)}</dd>
      </div>
    </dl>
  );
}
