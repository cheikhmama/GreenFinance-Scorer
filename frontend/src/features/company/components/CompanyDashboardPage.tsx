import { ArrowRight, Award, History } from "lucide-react";
import { Link } from "react-router-dom";
import type {
  NotificationPublic,
  RapportESGPublic,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { useMyNotifications } from "@/shared/notifications/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { useCompanyReports, useReportChecklist } from "../api";
import { libelleExercice, separerDeclarations, totaux } from "../session/etat";
import { dernierScoreAffichable, presentationSession } from "../session/presentation";
import { CompanyIdentityHeader } from "./CompanyIdentityHeader";

/** Jalons montrés dans le fil d'activité : les étapes internes de l'examen (affectation, avis)
 * restent hors du fil, comme du badge (tâches 5.1, 5.9). */
const JALONS: Record<string, string> = {
  RAPPORT_ANALYSE_TERMINEE: "Analyse du fichier terminée",
  RAPPORT_EXTRACTION_ECHOUEE: "Analyse du fichier échouée",
  RAPPORT_DEPOSE: "Rapport transmis",
  RAPPORT_CORRECTION_DEMANDEE: "Correction demandée",
  RAPPORT_VALIDE: "Score officiel publié",
  RAPPORT_REJETE: "Rapport rejeté",
  ENTREPRISE_PUBLIEE: "Fiche publiée aux investisseurs",
};

/** Tableau de bord Entreprise (tâche 5.9) : la session active, le dernier score officiel et les
 * jalons récents — la liste complète vit sur « Mes déclarations ». */
export function CompanyDashboardPage() {
  const { data: rapports, isPending } = useCompanyReports();
  const notifications = useMyNotifications(20);
  const { enCours, historique } = separerDeclarations(rapports ?? []);
  // Jamais l'exercice de la session en cours ni un plus récent à côté d'elle (tâche 5.9).
  const dernierScore = dernierScoreAffichable(historique, enCours[0]);
  const jalons = (notifications.data ?? []).filter((n) => n.type in JALONS).slice(0, 6);

  return (
    <div className="space-y-6">
      <CompanyIdentityHeader />

      <div className="grid gap-4 lg:grid-cols-2">
        {isPending ? <Skeleton className="h-44 w-full" /> : <SessionActive rapport={enCours[0]} />}
        {isPending ? <Skeleton className="h-44 w-full" /> : <DernierScore rapport={dernierScore} />}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
            <History className="size-4" aria-hidden="true" />
            Activité récente
          </CardTitle>
        </CardHeader>
        <CardContent>
          {notifications.isPending ? <Skeleton className="h-20 w-full" /> : null}
          {notifications.data && jalons.length === 0 ? (
            <p className="text-sm text-brand-grey">Aucun jalon pour l’instant.</p>
          ) : null}
          {jalons.length > 0 ? (
            <ol aria-label="Activité récente" className="divide-y">
              {jalons.map((jalon) => (
                <Jalon key={jalon.id} notification={jalon} />
              ))}
            </ol>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

function dateCourte(iso: string) {
  return new Date(iso).toLocaleDateString("fr-FR");
}

/** Carte « Session active » (tâche 5.9) : sobre, sans pastille ni bouton plein — l'exercice, sa
 * date, un encadré d'état en une phrase, et un lien vers le suivi. */
function SessionActive({ rapport }: { rapport: RapportESGPublic | undefined }) {
  const analyseReussie =
    rapport && rapport.extraction_error === null ? rapport.extraction_finished_at : null;
  const liste = useReportChecklist(rapport?.id ?? "", analyseReussie ?? null);
  const total = liste.data ? totaux(liste.data) : null;
  const presentation = rapport ? presentationSession(rapport.status) : null;
  const exercice = rapport ? libelleExercice(rapport.fiscal_year) : null;

  return (
    <section
      aria-label="Session active"
      className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950"
    >
      <div className="flex items-center justify-between border-b border-slate-100 pb-4 dark:border-slate-800">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Session active
        </span>
        {exercice ? <span className="text-xs text-slate-400">Exercice {exercice}</span> : null}
      </div>

      {rapport && presentation ? (
        <div className="py-4">
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
        <p className="py-4 text-sm text-slate-500">Aucune déclaration en cours.</p>
      )}

      <div className="pt-2">
        <Link
          to="/company/declarations"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 transition-colors hover:text-emerald-800 dark:text-emerald-400 dark:hover:text-emerald-300"
        >
          {rapport ? "Voir le suivi de la déclaration" : "Ouvrir une déclaration"}
          <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </div>
    </section>
  );
}

function DernierScore({ rapport }: { rapport: RapportESGPublic | undefined }) {
  return (
    <Card aria-label="Dernier score officiel" role="region">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
          <Award className="size-4" aria-hidden="true" />
          Dernier score officiel
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {rapport && rapport.official_global_score != null ? (
          <>
            <p className="text-sm text-brand-grey">{libelleExercice(rapport.fiscal_year)}</p>
            <p className="text-3xl font-semibold tabular-nums text-brand-blue">
              {rapport.official_global_score.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}
              <span className="text-base font-normal text-brand-grey">/100</span>
            </p>
            {rapport.coverage_rate != null ? (
              <p className="text-sm">
                Taux de couverture : {Math.round(rapport.coverage_rate * 100)} %
              </p>
            ) : null}
            {rapport.config_hash ? (
              <p className="text-xs text-brand-grey">
                Configuration de scoring :{" "}
                <code className="font-mono" title={rapport.config_hash}>
                  {rapport.config_hash.slice(0, 12)}…
                </code>
              </p>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-brand-grey">Aucun score officiel publié</p>
        )}
      </CardContent>
    </Card>
  );
}

function Jalon({ notification }: { notification: NotificationPublic }) {
  return (
    <li className="flex items-start justify-between gap-4 py-3 text-sm">
      <span>
        <span className="block font-medium text-brand-blue">{JALONS[notification.type]}</span>
        <span className="block text-brand-grey">{notification.message}</span>
      </span>
      <time className="shrink-0 text-xs text-brand-grey" dateTime={notification.sent_at}>
        {new Date(notification.sent_at).toLocaleDateString("fr-FR")}
      </time>
    </li>
  );
}
