import { ArrowRight, Award, FileClock, History } from "lucide-react";
import { Link } from "react-router-dom";
import type {
  NotificationPublic,
  RapportESGPublic,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  libelleStatutRapportEntreprise,
  variantStatutRapportEntreprise,
} from "@/shared/format/statut";
import { useMyNotifications } from "@/shared/notifications/api";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { Skeleton } from "@/shared/ui/skeleton";
import { useCompanyReports, useReportChecklist } from "../api";
import { libelleExercice, separerDeclarations, totaux } from "../session/etat";

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
  const dernierScore = historique
    .filter((r) => r.status === "VALIDATED" && r.official_global_score != null)
    .sort((a, b) => (b.submitted_at ?? "").localeCompare(a.submitted_at ?? ""))[0];
  const jalons = (notifications.data ?? []).filter((n) => n.type in JALONS).slice(0, 6);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Entreprise"
        title="Tableau de bord"
        description="Votre déclaration en cours, votre dernier score officiel et les derniers jalons."
      />

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

function SessionActive({ rapport }: { rapport: RapportESGPublic | undefined }) {
  const analyseReussie =
    rapport && rapport.extraction_error === null ? rapport.extraction_finished_at : null;
  const liste = useReportChecklist(rapport?.id ?? "", analyseReussie ?? null);
  const total = liste.data ? totaux(liste.data) : null;

  return (
    <Card aria-label="Session active" role="region">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
          <FileClock className="size-4" aria-hidden="true" />
          Session active
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {rapport ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-2xl font-semibold text-brand-blue">
                {libelleExercice(rapport.fiscal_year)}
              </span>
              <Badge
                variant={variantStatutRapportEntreprise(
                  rapport.status,
                  rapport.submitted_at !== null,
                )}
              >
                {libelleStatutRapportEntreprise(rapport.status, rapport.submitted_at !== null)}
              </Badge>
            </div>
            <p className="text-sm text-brand-grey">
              {total
                ? `${total.found}/${total.expected} indicateurs détectés`
                : rapport.status === "EXTRACTING" && rapport.submitted_at === null
                  ? "Analyse du fichier en cours"
                  : rapport.source_file === null
                    ? "Aucun fichier joint"
                    : "Complétude indisponible"}
            </p>
            <Button asChild>
              <Link to="/company/declarations">
                Accéder à ma déclaration en cours
                <ArrowRight />
              </Link>
            </Button>
          </>
        ) : (
          <>
            <p className="text-sm text-brand-grey">Aucune déclaration en cours.</p>
            <Button asChild variant="outline">
              <Link to="/company/declarations">
                Ouvrir une déclaration
                <ArrowRight />
              </Link>
            </Button>
          </>
        )}
      </CardContent>
    </Card>
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
          <p className="text-sm text-brand-grey">Aucun score officiel publié pour l’instant.</p>
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
