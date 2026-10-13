import {
  Briefcase,
  Building2,
  ClipboardCheck,
  FileCheck2,
  FileText,
  FlaskConical,
  FolderKanban,
  ThumbsDown,
  ThumbsUp,
  UserPlus,
  Wallet,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { PageHeader } from "@/shared/ui/page-header";
import { StatCard } from "@/shared/ui/stat-card";
import { useAdminDashboard, useApercuActeurs, usePendingRegistrations } from "../api";
import { EsgPerformanceSection } from "./EsgPerformanceSection";

/** Vue d'ensemble de l'espace Administrateur (/admin) : synthèse globale, statistiques par
 * acteur et performance ESG. Deux appels réseau distincts — useAdminDashboard
 * (TableauDeBordAdmin, la synthèse déjà en place) et useApercuActeurs (app/admin/apercu.py,
 * statistiques Auditeur/Investisseur/Chercheur/Institution) — jamais fusionnés en un seul gros
 * payload, chacun sert un usage différent (TableauDeBordAdmin reste utilisé seul par ailleurs).
 * Pas de section "accès rapides" séparée : la sidebar (roleNav.ts) donne déjà accès aux espaces
 * principaux. Pas de file de travail ("Actions prioritaires") ni d'aperçu du journal d'audit ici
 * : les deux restent accessibles depuis Rapports/Utilisateurs et Journal d'audit respectivement,
 * un tableau de bord n'a pas vocation à dupliquer ces files. */
export function AdminDashboardPage() {
  const { data } = useAdminDashboard();
  const { data: inscriptions } = usePendingRegistrations();
  const { data: apercu } = useApercuActeurs();

  return (
    <div className="space-y-8">
      <PageHeader title="Tableau de bord" />

      {inscriptions && inscriptions.length > 0 ? (
        <Alert className="border-amber-300 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/40">
          <UserPlus aria-hidden="true" className="text-amber-700 dark:text-amber-400" />
          <AlertTitle>
            {inscriptions.length} inscription{inscriptions.length > 1 ? "s" : ""} d’entreprise à
            valider
          </AlertTitle>
          <AlertDescription>
            <Link
              to="/admin/entreprises#inscriptions-a-valider"
              className="font-medium text-primary underline-offset-4 hover:underline"
            >
              Examiner les demandes
            </Link>
          </AlertDescription>
        </Alert>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-3" aria-label="Synthèse globale">
        <StatCard
          label="Entreprises inscrites"
          value={data?.registered_companies ?? "—"}
          hint="Toutes, publiées ou non"
          icon={<Building2 className="size-5" />}
          tone="blue"
          to="/admin/entreprises?onglet=inscrites"
        />
        <StatCard
          label="Entreprises publiées"
          value={data?.published_companies ?? "—"}
          hint="Fiche visible publiquement"
          icon={<Building2 className="size-5" />}
          tone="blue"
          to="/admin/entreprises?onglet=inscrites"
        />
        <StatCard
          label="Rapports soumis"
          value={data?.submitted_reports ?? "—"}
          hint="Dépôts initiaux et corrections"
          icon={<FileText className="size-5" />}
          tone="blue"
          to="/admin/rapports?onglet=tous"
        />
      </section>

      <section className="space-y-3" aria-label="Statistiques par acteur">
        <h2 className="text-base font-semibold text-foreground">Statistiques par acteur</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Entreprise
            </p>
            <StatCard
              label="Rapports validés"
              value={data?.validated_reports ?? "—"}
              hint="Décision favorable rendue"
              icon={<ThumbsUp className="size-5" />}
              to="/admin/rapports?onglet=tous&statut=VALIDATED"
            />
            <StatCard
              label="Rapports rejetés"
              value={data?.rejected_reports ?? "—"}
              hint="Décision défavorable rendue"
              icon={<ThumbsDown className="size-5" />}
              tone="violet"
              to="/admin/rapports?onglet=tous&statut=REJECTED"
            />
          </div>

          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Auditeur
            </p>
            <StatCard
              label="Auditeurs actifs"
              value={data?.active_auditors ?? "—"}
              hint="Comptes pouvant recevoir une affectation"
              icon={<ClipboardCheck className="size-5" />}
              to="/admin/utilisateurs?role=AUDITOR"
            />
            <StatCard
              label="Dossiers affectés"
              value={apercu?.auditors.assigned_reports ?? "—"}
              hint="Tous auditeurs confondus, en cours"
              icon={<FileText className="size-5" />}
              to="/admin/auditeurs"
            />
          </div>

          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Investisseur
            </p>
            <StatCard
              label="Investisseurs actifs"
              value={data?.active_investors ?? "—"}
              hint="Comptes consultant le catalogue publié"
              icon={<Wallet className="size-5" />}
              to="/admin/utilisateurs?role=INVESTOR"
            />
            <StatCard
              label="Portefeuilles non archivés"
              value={apercu?.investors.active_portfolios ?? "—"}
              hint="Tous Investisseurs confondus"
              icon={<Wallet className="size-5" />}
              to="/admin/portefeuilles"
            />
          </div>

          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Chercheur
            </p>
            <StatCard
              label="Chercheurs actifs"
              value={data?.active_researchers ?? "—"}
              hint="Comptes rattachables à un projet"
              icon={<FlaskConical className="size-5" />}
              to="/admin/utilisateurs?role=RESEARCHER"
            />
            <StatCard
              label="Analyses soumises"
              value={apercu?.researchers.submitted_analyses ?? "—"}
              hint="En attente d'examen par l'Institution"
              icon={<FileCheck2 className="size-5" />}
              to="/admin/analyses?statut=SOUMISE"
            />
          </div>

          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Institution
            </p>
            <StatCard
              label="Institutions actives"
              value={data?.active_institutions ?? "—"}
              hint="Comptes pouvant piloter des projets"
              icon={<Briefcase className="size-5" />}
              to="/admin/utilisateurs?role=INSTITUTION"
            />
            <StatCard
              label="Projets ouverts"
              value={apercu?.institutions.open_projects ?? "—"}
              hint="En cours"
              icon={<FolderKanban className="size-5" />}
              to="/admin/projets?statut=OUVERT"
            />
          </div>
        </div>
      </section>

      <section className="space-y-3" aria-label="Performance ESG">
        <h2 className="text-base font-semibold text-foreground">Performance ESG</h2>
        <EsgPerformanceSection />
      </section>
    </div>
  );
}
