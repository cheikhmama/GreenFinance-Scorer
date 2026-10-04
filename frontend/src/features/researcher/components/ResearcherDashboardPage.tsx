import { FlaskConical, FolderKanban, UserPlus } from "lucide-react";
import { Link } from "react-router-dom";
import { libelleStatutAnalyse, variantStatutAnalyse } from "@/shared/format/statutAnalyse";
import { libelleStatutProjet, variantStatutProjet } from "@/shared/format/statutProjet";
import { PageShell } from "@/shared/layout/PageShell";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { StatCard } from "@/shared/ui/stat-card";
import { useMyAnalyses, useMyAssignedProjects, useMyInvitations } from "../api";

const APERCU = 5;

function date(valeur: string | null): string | null {
  return valeur ? new Date(valeur).toLocaleDateString("fr-FR") : null;
}

/** Synthèse calculée côté client à partir des listes déjà exposées — aucune route de tableau de
 * bord dédiée côté backend (pas demandée pour cet espace, voir cahier des charges §Chercheur).
 * Au-delà des compteurs, ce qui appelle une action : analyses à corriger d'abord, puis les
 * dernières analyses et les projets avec leur échéance (tâche 5.14). */
export function ResearcherDashboardPage() {
  const { data: rattachements } = useMyInvitations();
  const { data: projets } = useMyAssignedProjects();
  const { data: analyses } = useMyAnalyses();

  const invitationsEnAttente = rattachements?.filter((r) => r.status === "EN_ATTENTE").length ?? 0;
  const aCorriger = analyses?.filter((a) => a.status === "CORRECTION_DEMANDEE") ?? [];
  // À corriger d'abord, puis les plus récentes.
  const dernieresAnalyses = [...(analyses ?? [])]
    .sort(
      (a, b) =>
        Number(b.status === "CORRECTION_DEMANDEE") - Number(a.status === "CORRECTION_DEMANDEE") ||
        b.created_at.localeCompare(a.created_at),
    )
    .slice(0, APERCU);

  return (
    <PageShell
      title="Tableau de bord"
      description="Vos projets, vos analyses et ce qui attend une action de votre part."
    >
      <section className="grid gap-4 sm:grid-cols-3" aria-label="Indicateurs clés">
        <StatCard
          label="Projets affectés"
          value={projets?.length ?? "—"}
          hint="Sur des institutions rattachées"
          icon={<FolderKanban className="size-5" />}
          to="/researcher/projets"
        />
        <StatCard
          label="Analyses"
          value={analyses?.length ?? "—"}
          hint="Toutes versions confondues"
          icon={<FlaskConical className="size-5" />}
          tone="blue"
          to="/researcher/analyses"
        />
        <StatCard
          label="Invitations en attente"
          value={invitationsEnAttente}
          hint="À accepter ou refuser"
          icon={<UserPlus className="size-5" />}
          tone="amber"
          to="/researcher/rattachements"
        />
      </section>

      {aCorriger.length > 0 ? (
        <Alert>
          <AlertTitle>
            {aCorriger.length === 1
              ? "Une analyse attend votre correction"
              : `${aCorriger.length} analyses attendent votre correction`}
          </AlertTitle>
          <AlertDescription>
            L’institution a demandé des modifications avant de décider.{" "}
            <Link
              to={`/researcher/analyses/${aCorriger[0].id}`}
              className="font-medium underline underline-offset-2"
            >
              Ouvrir « {aCorriger[0].title} »
            </Link>
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-4">
            <CardTitle className="text-base">Dernières analyses</CardTitle>
            <Button asChild variant="link" size="sm">
              <Link to="/researcher/analyses">Toutes les analyses</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {analyses && analyses.length === 0 ? (
              <EmptyState
                icon={FlaskConical}
                message="Aucune analyse pour l’instant — elles se rédigent depuis un projet."
              />
            ) : (
              <ul className="divide-y">
                {dernieresAnalyses.map((analyse) => (
                  <li key={analyse.id} className="flex items-center justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <Link
                        to={`/researcher/analyses/${analyse.id}`}
                        className="block truncate font-medium text-foreground hover:underline"
                      >
                        {analyse.title}
                      </Link>
                      <p className="text-xs text-muted-foreground">
                        Version {analyse.version}
                        {date(analyse.submitted_at)
                          ? ` · soumise le ${date(analyse.submitted_at)}`
                          : ` · créée le ${date(analyse.created_at)}`}
                      </p>
                    </div>
                    <Badge variant={variantStatutAnalyse(analyse.status)} className="shrink-0">
                      {libelleStatutAnalyse(analyse.status)}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-4">
            <CardTitle className="text-base">Mes projets</CardTitle>
            <Button asChild variant="link" size="sm">
              <Link to="/researcher/projets">Tous les projets</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {projets && projets.length === 0 ? (
              <EmptyState
                icon={FolderKanban}
                message="Aucun projet — une institution vous affecte à ses projets après votre rattachement."
              />
            ) : (
              <ul className="divide-y">
                {(projets ?? []).slice(0, APERCU).map((projet) => (
                  <li key={projet.id} className="flex items-center justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <Link
                        to={`/researcher/projets/${projet.id}`}
                        className="block truncate font-medium text-foreground hover:underline"
                      >
                        {projet.name}
                      </Link>
                      <p className="truncate text-xs text-muted-foreground">
                        {projet.institution_email}
                        {date(projet.deadline) ? ` · échéance le ${date(projet.deadline)}` : ""}
                      </p>
                    </div>
                    <Badge variant={variantStatutProjet(projet.status)} className="shrink-0">
                      {libelleStatutProjet(projet.status)}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </PageShell>
  );
}
