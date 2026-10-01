import { ArrowRight, CheckCircle2 } from "lucide-react";
import { Link } from "react-router-dom";
import type {
  NotificationPublic,
  RapportESGPublic,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { useMyNotifications } from "@/shared/notifications/api";
import { Button } from "@/shared/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { useCompanyReports, useReportChecklist } from "../api";
import { libelleExercice, separerDeclarations, totaux } from "../session/etat";
import { dernierScoreAffichable, presentationSession } from "../session/presentation";
import { CompanyIdentityHeader } from "./CompanyIdentityHeader";

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

/** Tableau de bord Entreprise (tâche 5.9) : l'identité de l'entreprise, la session active et le
 * dernier score officiel, puis les deux seuls jalons qui la concernent. Uniquement des composants
 * partagés (Card, Badge, Button) et des jetons de thème : rendu identique en clair et en sombre. */
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
      <CompanyIdentityHeader />

      <div className="grid gap-4 lg:grid-cols-2">
        {isPending ? <Skeleton className="h-64 w-full" /> : <SessionActive rapport={enCours[0]} />}
        {isPending ? <Skeleton className="h-64 w-full" /> : <DernierScore rapport={dernierScore} />}
      </div>

      {jalons.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Activité récente</CardTitle>
          </CardHeader>
          <CardContent>
            <ol aria-label="Activité récente" className="space-y-3">
              {jalons.map(({ notification, libelle }) => (
                <li
                  key={notification.id}
                  className="flex items-center justify-between gap-4 text-sm text-foreground"
                >
                  <span className="flex items-center gap-2">
                    <CheckCircle2 className="size-4 text-primary" aria-hidden="true" />
                    {libelle}
                  </span>
                  <time
                    className="shrink-0 text-xs text-muted-foreground"
                    dateTime={notification.sent_at}
                  >
                    {new Date(notification.sent_at).toLocaleDateString("fr-FR")}
                  </time>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function dateCourte(iso: string) {
  return new Date(iso).toLocaleDateString("fr-FR");
}

function SessionActive({ rapport }: { rapport: RapportESGPublic | undefined }) {
  const analyseReussie =
    rapport && rapport.extraction_error === null ? rapport.extraction_finished_at : null;
  const liste = useReportChecklist(rapport?.id ?? "", analyseReussie ?? null);
  const total = liste.data ? totaux(liste.data) : null;
  const presentation = rapport ? presentationSession(rapport.status) : null;
  const exercice = rapport ? libelleExercice(rapport.fiscal_year) : null;

  return (
    <Card role="region" aria-label="Session active">
      <CardHeader>
        <CardDescription className="text-xs font-semibold uppercase tracking-wider">
          Session active
        </CardDescription>
        {exercice ? (
          <CardAction className="text-xs text-muted-foreground">Exercice {exercice}</CardAction>
        ) : null}
        {rapport ? (
          <CardTitle className="text-2xl font-bold tracking-tight">
            <h2>{exercice}</h2>
          </CardTitle>
        ) : null}
      </CardHeader>
      <CardContent className="flex-1">
        {rapport && presentation ? (
          <div className="space-y-4">
            <p className="text-xs text-muted-foreground">
              {rapport.submitted_at
                ? `Transmission effectuée le ${dateCourte(rapport.submitted_at)}`
                : `Brouillon ouvert le ${dateCourte(rapport.created_at)}`}
            </p>
            <div className="rounded-lg border bg-muted/50 p-3">
              <p className="text-xs font-medium text-foreground">Statut : {presentation.libelle}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{presentation.description}</p>
              {total ? (
                <p className="mt-2 text-xs text-muted-foreground">
                  {total.found}/{total.expected} indicateurs détectés
                </p>
              ) : null}
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Aucune déclaration en cours.</p>
        )}
      </CardContent>
      <CardFooter>
        <Button asChild variant="link" size="sm" className="h-auto px-0">
          <Link to="/company/declarations">
            {rapport ? "Voir le suivi" : "Ouvrir une déclaration"}
            <ArrowRight aria-hidden="true" />
          </Link>
        </Button>
      </CardFooter>
    </Card>
  );
}

function DernierScore({ rapport }: { rapport: RapportESGPublic | undefined }) {
  const score = rapport?.official_global_score ?? null;
  const exercice = rapport && score !== null ? libelleExercice(rapport.fiscal_year) : null;
  return (
    <Card role="region" aria-label="Dernier score officiel">
      <CardHeader>
        <CardDescription className="text-xs font-semibold uppercase tracking-wider">
          Dernier score officiel
        </CardDescription>
        {exercice ? (
          <CardAction className="text-xs text-muted-foreground">Exercice {exercice}</CardAction>
        ) : null}
        {exercice ? (
          <CardTitle className="text-2xl font-bold tracking-tight">
            <h2>{exercice}</h2>
          </CardTitle>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-2">
        {rapport && score !== null ? (
          <>
            <p className="text-3xl font-semibold tabular-nums text-foreground">
              {score.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}
              <span className="text-base font-normal text-muted-foreground">/100</span>
            </p>
            {rapport.coverage_rate != null ? (
              <p className="text-xs text-muted-foreground">
                Taux de couverture : {Math.round(rapport.coverage_rate * 100)} %
              </p>
            ) : null}
            {rapport.config_hash ? (
              <p className="text-xs text-muted-foreground">
                Configuration de scoring :{" "}
                <code className="font-mono text-foreground" title={rapport.config_hash}>
                  {rapport.config_hash.slice(0, 12)}…
                </code>
              </p>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Aucun score officiel publié</p>
        )}
      </CardContent>
    </Card>
  );
}
