import { ArrowRight, FlaskConical, FolderKanban, UserCheck, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { libelleStatutProjet, variantStatutProjet } from "@/shared/format/statutProjet";
import { PageShell } from "@/shared/layout/PageShell";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { ProgressBar } from "@/shared/ui/progress-bar";
import { StatCard } from "@/shared/ui/stat-card";
import {
  useAvailableResearchers,
  useMyAnalysesForInstitution,
  useMyProjects,
  useMyResearchers,
} from "../api";

const APERCU = 5;

/** Synthèse calculée côté client à partir des listes déjà exposées — aucune route de tableau de
 * bord dédiée côté backend, même logique que ResearcherDashboardPage. */
export function InstitutionDashboardPage() {
  const { data: rattachements } = useMyResearchers();
  const { data: disponibles } = useAvailableResearchers();
  const { data: projets } = useMyProjects();
  const { data: analyses } = useMyAnalysesForInstitution();

  const chercheursAcceptes = rattachements?.filter((r) => r.status === "ACCEPTE").length ?? 0;
  const invitationsEnAttente = rattachements?.filter((r) => r.status === "EN_ATTENTE").length ?? 0;
  const projetsOuverts = projets?.filter((p) => p.status === "OUVERT").length ?? 0;
  const aDecider = (analyses ?? [])
    .filter((a) => a.status === "SOUMISE")
    .sort((a, b) => (a.submitted_at ?? "").localeCompare(b.submitted_at ?? ""));
  const analysesADecider = aDecider.length;
  // Projets ouverts d'abord, échéance la plus proche en tête.
  const projetsTries = [...(projets ?? [])].sort(
    (a, b) =>
      Number(b.status === "OUVERT") - Number(a.status === "OUVERT") ||
      (a.deadline ?? "9999").localeCompare(b.deadline ?? "9999"),
  );

  // Taux réel d'acceptation des invitations envoyées — jamais un pourcentage fabriqué (ex. un
  // quota d'export sans plafond connu côté API, voir InstitutionProfilPublic) : ce ratio se
  // calcule entièrement à partir de données déjà chargées ici.
  const invitationsEnvoyees = rattachements?.length ?? 0;
  const tauxAcceptation =
    invitationsEnvoyees > 0 ? Math.round((chercheursAcceptes / invitationsEnvoyees) * 100) : 0;

  return (
    <PageShell
      title="Tableau de bord"
      description="Vos chercheurs, vos projets et les analyses qui attendent votre décision."
    >
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Indicateurs clés">
        <StatCard
          label="Chercheurs rattachés"
          value={chercheursAcceptes}
          hint="Invitations acceptées"
          icon={<UserCheck className="size-5" />}
          to="/institution/chercheurs"
        />
        <StatCard
          label="Projets ouverts"
          value={projetsOuverts}
          hint={`Sur ${projets?.length ?? 0} projet(s) au total`}
          icon={<FolderKanban className="size-5" />}
          tone="blue"
          to="/institution/projets"
        />
        <StatCard
          label="Analyses à décider"
          value={analysesADecider}
          hint="En attente de votre décision"
          icon={<FlaskConical className="size-5" />}
          tone="amber"
          to="/institution/analyses"
        />
        <StatCard
          label="Chercheurs disponibles"
          value={disponibles?.length ?? "—"}
          hint="Jamais encore invités"
          icon={<Users className="size-5" />}
          tone="violet"
          to="/institution/chercheurs"
        />
      </section>

      {invitationsEnvoyees > 0 ? (
        <Card>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-medium text-foreground">
                Taux d'acceptation des invitations
              </span>
              <span className="text-muted-foreground">
                {chercheursAcceptes}/{invitationsEnvoyees} accepté(s)
              </span>
            </div>
            <ProgressBar value={tauxAcceptation} />
          </CardContent>
        </Card>
      ) : null}

      {invitationsEnAttente > 0 ? (
        <Link
          to="/institution/chercheurs"
          className="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm font-medium text-amber-800 transition hover:border-amber-300"
        >
          {invitationsEnAttente} invitation{invitationsEnAttente > 1 ? "s" : ""} en attente de
          réponse
          <ArrowRight className="size-4" />
        </Link>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-4">
            <CardTitle className="text-base">Analyses à décider</CardTitle>
            <Button asChild variant="link" size="sm">
              <Link to="/institution/analyses">Toutes les analyses</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {aDecider.length === 0 ? (
              <EmptyState icon={FlaskConical} message="Aucune analyse en attente de décision." />
            ) : (
              <ul className="divide-y">
                {aDecider.slice(0, APERCU).map((analyse) => (
                  <li key={analyse.id} className="flex items-center justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <Link
                        to={`/institution/analyses/${analyse.id}`}
                        className="block truncate font-medium text-foreground hover:underline"
                      >
                        {analyse.title}
                      </Link>
                      <p className="truncate text-xs text-muted-foreground">
                        {analyse.project_name} · version {analyse.version}
                        {analyse.submitted_at
                          ? ` · soumise le ${new Date(analyse.submitted_at).toLocaleDateString("fr-FR")}`
                          : ""}
                      </p>
                    </div>
                    <Button asChild size="sm" variant="outline" className="shrink-0">
                      <Link to={`/institution/analyses/${analyse.id}`}>Décider</Link>
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-4">
            <CardTitle className="text-base">Projets</CardTitle>
            <Button asChild variant="link" size="sm">
              <Link to="/institution/projets">Tous les projets</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {projets && projets.length === 0 ? (
              <EmptyState icon={FolderKanban} message="Aucun projet pour l’instant." />
            ) : (
              <ul className="divide-y">
                {projetsTries.slice(0, APERCU).map((projet) => (
                  <li key={projet.id} className="flex items-center justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <Link
                        to={`/institution/projets/${projet.id}`}
                        className="block truncate font-medium text-foreground hover:underline"
                      >
                        {projet.name}
                      </Link>
                      <p className="text-xs text-muted-foreground">
                        {projet.deadline
                          ? `Échéance le ${new Date(projet.deadline).toLocaleDateString("fr-FR")}`
                          : "Sans échéance"}
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
