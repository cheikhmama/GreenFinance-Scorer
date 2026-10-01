import { FlaskConical, FolderKanban, UserPlus } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/shared/ui/page-header";
import { StatCard } from "@/shared/ui/stat-card";
import { useMyAnalyses, useMyAssignedProjects, useMyInvitations } from "../api";

/** Synthèse calculée côté client à partir des listes déjà exposées — aucune route de tableau de
 * bord dédiée côté backend (pas demandée pour cet espace, voir cahier des charges §Chercheur). */
export function ResearcherDashboardPage() {
  const { data: rattachements } = useMyInvitations();
  const { data: projets } = useMyAssignedProjects();
  const { data: analyses } = useMyAnalyses();

  const invitationsEnAttente = rattachements?.filter((r) => r.status === "EN_ATTENTE").length ?? 0;
  const correctionsAttendues =
    analyses?.filter((a) => a.status === "CORRECTION_DEMANDEE").length ?? 0;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Chercheur"
        title="Tableau de bord"
        description="Vue d'ensemble de vos rattachements, projets et analyses."
      />

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
        />
        <StatCard
          label="Invitations en attente"
          value={invitationsEnAttente}
          hint="À accepter ou refuser"
          icon={<UserPlus className="size-5" />}
          tone="amber"
        />
      </section>

      {correctionsAttendues > 0 ? (
        <Link
          to="/researcher/analyses"
          className="block rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 hover:bg-amber-100"
        >
          {correctionsAttendues} analyse(s) en attente de correction — voir « Analyses ».
        </Link>
      ) : null}
    </div>
  );
}
