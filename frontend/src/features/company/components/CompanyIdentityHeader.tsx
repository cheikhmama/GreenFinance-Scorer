import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";
import { Skeleton } from "@/shared/ui/skeleton";
import { useMyCompanyProfile, useMyLeiVerification } from "../api";

/** En-tête de l'espace Entreprise (tâche 5.9) : le nom légal de l'entreprise connectée, puis
 * secteur, LEI et ISIN tels que déclarés. Le badge « GLEIF Validé » n'apparaît que si la GLEIF
 * confirme, en direct, l'enregistrement et le nom légal ; rien n'est affiché à la place d'une
 * donnée manquante. */
export function CompanyIdentityHeader({ action }: { action?: ReactNode }) {
  const { data: entreprise, isPending } = useMyCompanyProfile();
  const verification = useMyLeiVerification(entreprise?.lei);

  if (isPending) return <Skeleton className="mb-6 h-14 w-2/3" />;
  if (!entreprise) return null;

  return (
    <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <div className="mb-1 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-50">
            {entreprise.name}
          </h1>
          {verification.data?.result === "PASSED" ? (
            <span
              className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-300"
              title={verification.data.detail}
            >
              <CheckCircle2 className="h-3 w-3 text-emerald-600" aria-hidden="true" />
              GLEIF Validé
            </span>
          ) : null}
          {verification.data?.result === "FAILED" ? (
            <span
              className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-300"
              title={verification.data.detail}
            >
              <AlertTriangle className="h-3 w-3" aria-hidden="true" />
              LEI non confirmé par la GLEIF
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
          <span>
            Secteur :{" "}
            <strong className="font-semibold text-slate-700 dark:text-slate-200">
              {entreprise.sector}
            </strong>
          </span>
          {entreprise.lei ? (
            <>
              <span aria-hidden="true">•</span>
              <span>
                LEI :{" "}
                <code className="font-mono text-slate-700 dark:text-slate-200">
                  {entreprise.lei}
                </code>
              </span>
            </>
          ) : null}
          {entreprise.isin ? (
            <>
              <span aria-hidden="true">•</span>
              <span>
                ISIN :{" "}
                <code className="font-mono text-slate-700 dark:text-slate-200">
                  {entreprise.isin}
                </code>
              </span>
            </>
          ) : null}
        </div>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </header>
  );
}
