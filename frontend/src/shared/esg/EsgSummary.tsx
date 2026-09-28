import type {
  DonneesCarboneAgregees,
  ScoreEntreprisePublic,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { formatScore } from "@/shared/format/etatPosition";

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
        <dd className="mt-0.5 font-semibold text-brand-blue">{formatScore(score.valeur_globale)}</dd>
        <BarreScore valeur={score.valeur_globale} teinte={TEINTES_PILIER.global} />
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">E</dt>
        <dd className="mt-0.5 font-semibold text-brand-blue">{formatScore(score.score_environnement)}</dd>
        <BarreScore valeur={score.score_environnement} teinte={TEINTES_PILIER.E} />
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">S</dt>
        <dd className="mt-0.5 font-semibold text-brand-blue">{formatScore(score.score_social)}</dd>
        <BarreScore valeur={score.score_social} teinte={TEINTES_PILIER.S} />
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide text-muted-foreground">G</dt>
        <dd className="mt-0.5 font-semibold text-brand-blue">{formatScore(score.score_gouvernance)}</dd>
        <BarreScore valeur={score.score_gouvernance} teinte={TEINTES_PILIER.G} />
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
