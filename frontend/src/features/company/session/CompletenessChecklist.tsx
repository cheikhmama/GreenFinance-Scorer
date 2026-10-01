import type { GroupeCompletude } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleGroupe, totaux } from "./etat";

/** Liste de complétude d'un brouillon analysé (tâche 5.8) : par groupe, combien d'indicateurs
 * attendus ont été trouvés dans le fichier — des comptes, jamais de valeurs ni de score. */
export function CompletenessChecklist({ groupes }: { groupes: GroupeCompletude[] }) {
  const total = totaux(groupes);
  return (
    <section aria-label="Liste de complétude" className="space-y-3">
      <p className="text-sm text-brand-grey">
        {total.found} indicateur(s) trouvé(s) sur {total.expected} attendus. Les valeurs ne sont pas
        affichées : elles seront relues par l’auditeur après la soumission.
      </p>
      <ul className="divide-y rounded-lg border">
        {groupes.map((groupe) => {
          const manquants = groupe.expected - groupe.found;
          const part = groupe.expected ? Math.round((groupe.found / groupe.expected) * 100) : 0;
          return (
            <li key={groupe.group} className="space-y-2 p-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                <span className="font-medium text-brand-blue">{libelleGroupe(groupe.group)}</span>
                <span className="tabular-nums">
                  {groupe.found} / {groupe.expected} trouvé(s)
                  {manquants > 0 ? (
                    <span className="ml-2 text-brand-grey">· {manquants} manquant(s)</span>
                  ) : null}
                </span>
              </div>
              <div
                className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"
                role="progressbar"
                aria-label={libelleGroupe(groupe.group)}
                aria-valuemin={0}
                aria-valuemax={groupe.expected}
                aria-valuenow={groupe.found}
              >
                <div className="h-full rounded-full bg-brand-green" style={{ width: `${part}%` }} />
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
