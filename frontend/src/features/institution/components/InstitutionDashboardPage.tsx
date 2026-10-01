import { ArrowRight, FlaskConical, FolderKanban, UserCheck, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { ProgressBar } from "@/shared/ui/progress-bar";
import { StatCard } from "@/shared/ui/stat-card";
import {
  useAvailableResearchers,
  useMyAnalysesForInstitution,
  useMyProjects,
  useMyResearchers,
} from "../api";

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
  const analysesADecider = analyses?.filter((a) => a.status === "SOUMISE").length ?? 0;

  // Taux réel d'acceptation des invitations envoyées — jamais un pourcentage fabriqué (ex. un
  // quota d'export sans plafond connu côté API, voir InstitutionProfilPublic) : ce ratio se
  // calcule entièrement à partir de données déjà chargées ici.
  const invitationsEnvoyees = rattachements?.length ?? 0;
  const tauxAcceptation =
    invitationsEnvoyees > 0 ? Math.round((chercheursAcceptes / invitationsEnvoyees) * 100) : 0;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Institution"
        title="Tableau de bord"
        description="Vue d'ensemble de vos chercheurs rattachés, de vos projets et des analyses à décider."
      />

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
              <span className="font-medium text-brand-blue">
                Taux d'acceptation des invitations
              </span>
              <span className="text-brand-grey">
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

      <Link
        to="/institution/projets"
        className="flex items-center justify-between rounded-xl border border-border bg-muted p-4 text-sm font-medium text-brand-blue transition hover:border-brand-green"
      >
        Voir tous les projets
        <ArrowRight className="size-4" />
      </Link>
    </div>
  );
}
