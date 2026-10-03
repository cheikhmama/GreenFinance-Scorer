import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { ApiError } from "@/shared/api/errors";
import { getScoreExplanation } from "@/shared/api/generated/explainability/explainability";
import {
  BaselineScope,
  type MetricContribution,
  type ScoreExplanation,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { Skeleton } from "@/shared/ui/skeleton";
import { libelleIndicateur } from "@/shared/format/indicateurs";

const LIBELLES_PILIER: Record<string, string> = {
  ENVIRONNEMENT: "Environnement",
  SOCIAL: "Social",
  GOUVERNANCE: "Gouvernance",
};

function points(valeur: number): string {
  const signe = valeur > 0 ? "+" : valeur < 0 ? "−" : "±";
  return `${signe}${Math.abs(valeur).toLocaleString("fr-FR", { maximumFractionDigits: 1 })}`;
}

function note(valeur: number): string {
  return valeur.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
}

/** Barre posée sur une piste 0-100 : de `debut` à `fin` (dans n'importe quel ordre). */
function Barre({ debut, fin, teinte }: { debut: number; fin: number; teinte: string }) {
  const gauche = Math.max(0, Math.min(debut, fin));
  const largeur = Math.max(0.5, Math.min(100, Math.max(debut, fin)) - gauche);
  return (
    <div className="relative h-3 w-full rounded bg-muted">
      <div
        className={`absolute top-0 h-3 rounded ${teinte}`}
        style={{ left: `${gauche}%`, width: `${largeur}%` }}
      />
    </div>
  );
}

function Ligne({
  libelle,
  valeur,
  debut,
  fin,
  teinte,
  aide,
}: {
  libelle: string;
  valeur: string;
  debut: number;
  fin: number;
  teinte: string;
  aide?: string;
}) {
  return (
    <li className="grid grid-cols-[minmax(0,18rem)_1fr_4.5rem] items-center gap-3 text-sm">
      <span className="truncate" title={aide ? `${libelle} — ${aide}` : libelle}>
        {libelle}
        {aide ? <span className="text-xs text-brand-grey"> ({aide})</span> : null}
      </span>
      <Barre debut={debut} fin={fin} teinte={teinte} />
      <span className="text-right tabular-nums">{valeur}</span>
    </li>
  );
}

/** Cascade : score de référence, puis chaque indicateur, pilier par pilier, jusqu'au score. */
function Cascade({ explication }: { explication: ScoreExplanation }) {
  const lignes: React.ReactNode[] = [];
  let cumul = explication.baseline_score;
  let piliers = new Map<string, MetricContribution[]>();
  for (const contribution of explication.contributions) {
    piliers = piliers.set(contribution.pillar, [
      ...(piliers.get(contribution.pillar) ?? []),
      contribution,
    ]);
  }
  for (const pilier of explication.pillars) {
    lignes.push(
      <li
        key={`pilier-${pilier.pillar}`}
        className="pt-2 text-xs font-medium uppercase tracking-wide text-muted-foreground"
      >
        {LIBELLES_PILIER[pilier.pillar] ?? pilier.pillar} · {points(pilier.contribution)} pts
      </li>,
    );
    for (const contribution of piliers.get(pilier.pillar) ?? []) {
      const debut = cumul;
      cumul += contribution.contribution;
      lignes.push(
        <Ligne
          key={contribution.metric_code}
          libelle={libelleIndicateur(contribution.metric_code)}
          valeur={points(contribution.contribution)}
          debut={debut}
          fin={cumul}
          teinte={contribution.contribution >= 0 ? "bg-brand-green" : "bg-destructive"}
          aide={contribution.baseline_value === null ? "aucun pair ne le publie" : undefined}
        />,
      );
    }
  }
  return (
    <ol className="space-y-1.5">
      <Ligne
        libelle="Score de référence"
        valeur={note(explication.baseline_score)}
        debut={0}
        fin={explication.baseline_score}
        teinte="bg-slate-400"
      />
      {lignes}
      <li className="pt-2" />
      <Ligne
        libelle="Score"
        valeur={note(explication.score)}
        debut={0}
        fin={explication.score}
        teinte="bg-brand-blue"
      />
    </ol>
  );
}

/** Décomposition exacte du score officiel d'un rapport (tâche 3.2) : chaque indicateur ajoute ou
 * retire des points par rapport à la moyenne de ses pairs, et la somme retombe exactement sur le
 * score (SHAP linéaire, voir app/explainability/decomposition.py). */
export function ScoreWaterfall({ rapportId }: { rapportId: string }) {
  const [portee, setPortee] = useState<BaselineScope>(BaselineScope.SECTOR);
  const { data, isLoading, isError } = useQuery<ScoreExplanation, ApiError>({
    queryKey: ["score-explanation", rapportId, portee],
    queryFn: () => getScoreExplanation(rapportId, { baseline: portee }),
  });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-brand-grey">
          {data
            ? data.baseline.used === BaselineScope.SECTOR
              ? `Comparé à ${data.baseline.peer_count} entreprise(s) du secteur ${data.baseline.sector}.`
              : `Comparé à ${data.baseline.peer_count} entreprise(s) publiée(s), tous secteurs.`
            : "Comparaison avec les pairs"}
          {data && data.baseline.requested !== data.baseline.used
            ? " Trop peu de pairs dans le secteur : repli sur toutes les entreprises."
            : null}
        </p>
        <fieldset className="flex gap-1">
          <legend className="sr-only">Ensemble de référence</legend>
          {[
            [BaselineScope.SECTOR, "Secteur"],
            [BaselineScope.UNIVERSE, "Toutes les entreprises"],
          ].map(([valeur, libelle]) => (
            <button
              key={valeur}
              type="button"
              aria-pressed={portee === valeur}
              onClick={() => setPortee(valeur as BaselineScope)}
              className={`rounded-md border px-2 py-1 text-xs ${portee === valeur ? "bg-brand-blue text-white" : ""}`}
            >
              {libelle}
            </button>
          ))}
        </fieldset>
      </div>
      {isLoading ? <Skeleton className="h-40 w-full" /> : null}
      {isError ? (
        <p className="text-sm text-destructive">Décomposition du score indisponible.</p>
      ) : null}
      {data ? <Cascade explication={data} /> : null}
    </div>
  );
}
