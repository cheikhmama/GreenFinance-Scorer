import {
  Building2,
  ClipboardCheck,
  FileCheck2,
  FileText,
  FileWarning,
  ThumbsDown,
  ThumbsUp,
  UserCog,
} from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { StatCard } from "@/shared/ui/stat-card";
import { useAdminDashboard } from "../api";

/** Vue d'ensemble de l'espace Administrateur (/admin) — indicateurs clés et actions prioritaires.
 * Pas de section "accès rapides" séparée : la sidebar (roleNav.ts) donne déjà accès à chaque
 * espace, la dupliquer ici serait une redondance pure. Un seul appel réseau (GET /admin/dashboard)
 * plutôt qu'un par tuile — voir app/admin/dashboard.py::construire_tableau_de_bord. */
export function AdminDashboardPage() {
  const { data } = useAdminDashboard();
  const aucuneActionPrioritaire =
    data !== undefined &&
    data.rapports_a_affecter === 0 &&
    data.decisions_a_rendre === 0 &&
    data.demandes_republication === 0 &&
    data.utilisateurs_en_attente === 0;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Tableau de bord"
        description="Vue d'ensemble de la plateforme et des files de travail nécessitant une intervention."
      />

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Indicateurs clés">
        <StatCard
          label="Entreprises inscrites"
          value={data?.entreprises_inscrites ?? "—"}
          hint="Toutes, publiées ou non"
          icon={<Building2 className="size-5" />}
          tone="blue"
        />
        <StatCard
          label="Rapports soumis"
          value={data?.rapports_soumis ?? "—"}
          hint="Dépôts initiaux et corrections"
          icon={<FileText className="size-5" />}
          tone="blue"
        />
        <StatCard
          label="Rapports validés"
          value={data?.rapports_valides ?? "—"}
          hint="Décision favorable rendue"
          icon={<ThumbsUp className="size-5" />}
        />
        <StatCard
          label="Rapports rejetés"
          value={data?.rapports_rejetes ?? "—"}
          hint="Décision défavorable rendue"
          icon={<ThumbsDown className="size-5" />}
          tone="violet"
        />
        <StatCard
          label="Entreprises publiées"
          value={data?.entreprises_publiees ?? "—"}
          hint="Fiche visible publiquement"
          icon={<Building2 className="size-5" />}
        />
        <StatCard
          label="Audits en retard"
          value={data?.audits_en_retard ?? "—"}
          hint="Affecté au-delà du délai attendu"
          icon={<FileWarning className="size-5" />}
          tone="amber"
        />
      </section>

      <Card className="gap-0 py-0 shadow-none">
        <CardHeader className="border-b px-5 py-5">
          <CardTitle className="text-base text-brand-blue">Actions prioritaires</CardTitle>
        </CardHeader>
        <CardContent className="divide-y p-0">
          {aucuneActionPrioritaire ? (
            <p className="px-5 py-4 text-sm text-brand-grey">Rien à traiter pour l'instant.</p>
          ) : null}
          <ActionLigne
            to="/admin/rapports"
            label="Rapports à affecter"
            count={data?.rapports_a_affecter}
            icon={<ClipboardCheck className="size-4" />}
          />
          <ActionLigne
            to="/admin/rapports"
            label="Décisions à rendre"
            count={data?.decisions_a_rendre}
            icon={<FileCheck2 className="size-4" />}
          />
          <ActionLigne
            to="/admin/entreprises"
            label="Demandes de republication"
            count={data?.demandes_republication}
            icon={<Building2 className="size-4" />}
          />
          <ActionLigne
            to="/admin/utilisateurs"
            label="Utilisateurs en attente"
            count={data?.utilisateurs_en_attente}
            icon={<UserCog className="size-4" />}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function ActionLigne({
  to,
  label,
  count,
  icon,
}: {
  to: string;
  label: string;
  count: number | undefined;
  icon: ReactNode;
}) {
  if (count === 0) return null;

  return (
    <Link
      to={to}
      className="flex items-center justify-between gap-4 px-5 py-4 transition hover:bg-slate-50"
    >
      <div className="flex items-center gap-3">
        <span className="grid size-8 place-items-center rounded-lg bg-amber-50 text-amber-700">
          {icon}
        </span>
        <p className="text-sm font-medium text-brand-blue">{label}</p>
      </div>
      <span className="text-sm font-semibold tabular-nums text-brand-blue">{count ?? "—"}</span>
    </Link>
  );
}

