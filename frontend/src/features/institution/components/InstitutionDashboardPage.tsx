import { FolderKanban, UserCheck, UserPlus } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/shared/ui/page-header";
import { StatCard } from "@/shared/ui/stat-card";
import { useMyProjects, useMyResearchers } from "../api";

/** Synthèse calculée côté client à partir des listes déjà exposées — aucune route de tableau de
 * bord dédiée côté backend, même logique que ResearcherDashboardPage. */
export function InstitutionDashboardPage() {
  const { data: rattachements } = useMyResearchers();
  const { data: projets } = useMyProjects();

  const chercheursAcceptes = rattachements?.filter((r) => r.statut === "ACCEPTE").length ?? 0;
  const invitationsEnAttente = rattachements?.filter((r) => r.statut === "EN_ATTENTE").length ?? 0;
  const projetsOuverts = projets?.filter((p) => p.statut === "OUVERT").length ?? 0;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Institution"
        title="Tableau de bord"
        description="Vue d'ensemble de vos chercheurs rattachés et de vos projets."
      />

      <section className="grid gap-4 sm:grid-cols-3" aria-label="Indicateurs clés">
        <StatCard
          label="Chercheurs rattachés"
          value={chercheursAcceptes}
          hint="Invitations acceptées"
          icon={<UserCheck className="size-5" />}
        />
        <StatCard
          label="Projets ouverts"
          value={projetsOuverts}
          hint={`Sur ${projets?.length ?? 0} projet(s) au total`}
          icon={<FolderKanban className="size-5" />}
          tone="blue"
        />
        <StatCard
          label="Invitations en attente"
          value={invitationsEnAttente}
          hint="Réponse du chercheur attendue"
          icon={<UserPlus className="size-5" />}
          tone="amber"
        />
      </section>

      <Link
        to="/institution/projets"
        className="block rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-brand-blue hover:bg-slate-100"
      >
        Voir tous les projets et les analyses en attente de décision →
      </Link>
    </div>
  );
}
