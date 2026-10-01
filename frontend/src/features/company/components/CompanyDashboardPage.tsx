import { ArrowRight, CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type {
  NotificationPublic,
  RapportESGPublic,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { useMyNotifications } from "@/shared/notifications/api";
import { Skeleton } from "@/shared/ui/skeleton";
import {
  useCompanyReports,
  useMyCompanyProfile,
  useMyLeiVerification,
  useReportChecklist,
} from "../api";
import { libelleExercice, separerDeclarations, totaux } from "../session/etat";
import { dernierScoreAffichable, presentationSession } from "../session/presentation";

/** Les seuls jalons montrés à l'Entreprise : la transmission de son rapport et la publication de
 * son score. Les étapes internes (lecture du fichier, affectation, avis) n'y figurent jamais. */
function libelleJalon(type: string, exercice: string | null): string | null {
  const fy = exercice ? ` ${exercice}` : "";
  if (type === "RAPPORT_DEPOSE") return `Rapport${fy} transmis avec succès pour audit.`;
  if (type === "RAPPORT_VALIDE") {
    return exercice
      ? `Score officiel publié pour l’exercice ${exercice}.`
      : "Score officiel publié.";
  }
  return null;
}

function Carte({
  titre,
  coin,
  children,
}: {
  titre: string;
  coin?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      aria-label={titre}
      className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950"
    >
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 pb-4 dark:border-slate-800">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          {titre}
        </span>
        {coin ? <span className="text-xs text-slate-400">{coin}</span> : null}
      </div>
      {children}
    </section>
  );
}

/** Tableau de bord Entreprise (tâche 5.9) : la session active, avec l'identité de l'entreprise,
 * et le dernier score officiel ; puis les deux seuls jalons qui la concernent. Le détail des
 * déclarations vit sur « Mes déclarations ». */
export function CompanyDashboardPage() {
  const { data: rapports, isPending } = useCompanyReports();
  const notifications = useMyNotifications(20);
  const { enCours, historique } = separerDeclarations(rapports ?? []);
  // Jamais l'exercice de la session en cours ni un plus récent à côté d'elle.
  const dernierScore = dernierScoreAffichable(historique, enCours[0]);
  const exerciceDe = new Map((rapports ?? []).map((r) => [r.id, libelleExercice(r.fiscal_year)]));
  const jalons = (notifications.data ?? [])
    .map((n) => ({
      notification: n,
      libelle: libelleJalon(n.type, n.resource_id ? (exerciceDe.get(n.resource_id) ?? null) : null),
    }))
    .filter((j): j is { notification: NotificationPublic; libelle: string } => j.libelle !== null)
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-50">
        Tableau de bord
      </h1>

      <div className="grid gap-4 lg:grid-cols-2">
        {isPending ? <Skeleton className="h-56 w-full" /> : <SessionActive rapport={enCours[0]} />}
        {isPending ? <Skeleton className="h-56 w-full" /> : <DernierScore rapport={dernierScore} />}
      </div>

      {jalons.length > 0 ? (
        <section aria-labelledby="titre-jalons" className="space-y-2">
          <h2
            id="titre-jalons"
            className="text-xs font-semibold uppercase tracking-wider text-slate-400"
          >
            Activité récente
          </h2>
          <ol aria-label="Activité récente" className="space-y-2">
            {jalons.map(({ notification, libelle }) => (
              <li
                key={notification.id}
                className="flex items-center justify-between gap-4 text-sm text-slate-700 dark:text-slate-200"
              >
                <span className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                  {libelle}
                </span>
                <time className="shrink-0 text-xs text-slate-400" dateTime={notification.sent_at}>
                  {new Date(notification.sent_at).toLocaleDateString("fr-FR")}
                </time>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </div>
  );
}

function dateCourte(iso: string) {
  return new Date(iso).toLocaleDateString("fr-FR");
}

/** Identité de l'entreprise connectée, telle que déclarée ; « GLEIF Validé » seulement sur un
 * contrôle GLEIF réussi, jamais une valeur de remplacement. */
function Identite() {
  const { data: entreprise } = useMyCompanyProfile();
  const verification = useMyLeiVerification(entreprise?.lei);
  if (!entreprise) return null;
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">{entreprise.name}</p>
        {verification.data?.result === "PASSED" ? (
          <span
            className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-300"
            title={verification.data.detail}
          >
            <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
            GLEIF Validé
          </span>
        ) : null}
      </div>
      <p className="flex flex-wrap gap-x-3 text-xs text-slate-500">
        <span>Secteur : {entreprise.sector}</span>
        {entreprise.lei ? (
          <span>
            LEI :{" "}
            <code className="font-mono text-slate-700 dark:text-slate-200">{entreprise.lei}</code>
          </span>
        ) : null}
      </p>
    </div>
  );
}

function SessionActive({ rapport }: { rapport: RapportESGPublic | undefined }) {
  const analyseReussie =
    rapport && rapport.extraction_error === null ? rapport.extraction_finished_at : null;
  const liste = useReportChecklist(rapport?.id ?? "", analyseReussie ?? null);
  const total = liste.data ? totaux(liste.data) : null;
  const presentation = rapport ? presentationSession(rapport.status) : null;
  const exercice = rapport ? libelleExercice(rapport.fiscal_year) : null;

  return (
    <Carte titre="Session active" coin={exercice ? `Exercice ${exercice}` : undefined}>
      <div className="space-y-4 py-4">
        <Identite />
        {rapport && presentation ? (
          <div>
            <h3 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-50">
              {exercice}
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              {rapport.submitted_at
                ? `Transmission effectuée le ${dateCourte(rapport.submitted_at)}`
                : `Brouillon ouvert le ${dateCourte(rapport.created_at)}`}
            </p>
            <div className="mt-4 rounded-lg border border-slate-100 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-900">
              <div className="text-xs font-medium text-slate-700 dark:text-slate-200">
                Statut : {presentation.libelle}
              </div>
              <div className="mt-0.5 text-xs text-slate-500">{presentation.description}</div>
              {total ? (
                <div className="mt-2 text-xs text-slate-500">
                  {total.found}/{total.expected} indicateurs détectés
                </div>
              ) : null}
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-500">Aucune déclaration en cours.</p>
        )}
      </div>
      <Link
        to="/company/declarations"
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 transition-colors hover:text-emerald-800 dark:text-emerald-400 dark:hover:text-emerald-300"
      >
        {rapport ? "Voir le suivi" : "Ouvrir une déclaration"}
        <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
      </Link>
    </Carte>
  );
}

function DernierScore({ rapport }: { rapport: RapportESGPublic | undefined }) {
  const publie = rapport && rapport.official_global_score != null ? rapport : undefined;
  const exercice = publie ? libelleExercice(publie.fiscal_year) : null;
  return (
    <Carte titre="Dernier score officiel" coin={exercice ? `Exercice ${exercice}` : undefined}>
      <div className="space-y-2 py-4">
        {publie && publie.official_global_score != null ? (
          <>
            <h3 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-50">
              {exercice}
            </h3>
            <p className="text-3xl font-semibold tabular-nums text-slate-900 dark:text-slate-50">
              {publie.official_global_score.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}
              <span className="text-base font-normal text-slate-400">/100</span>
            </p>
            {publie.coverage_rate != null ? (
              <p className="text-xs text-slate-500">
                Taux de couverture : {Math.round(publie.coverage_rate * 100)} %
              </p>
            ) : null}
            {publie.config_hash ? (
              <p className="text-xs text-slate-500">
                Configuration de scoring :{" "}
                <code className="font-mono" title={publie.config_hash}>
                  {publie.config_hash.slice(0, 12)}…
                </code>
              </p>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-slate-500">Aucun score officiel publié</p>
        )}
      </div>
    </Carte>
  );
}
