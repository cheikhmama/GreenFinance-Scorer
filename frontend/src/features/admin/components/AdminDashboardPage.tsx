import {
  AlertTriangle,
  Briefcase,
  Building2,
  ChevronRight,
  ClipboardCheck,
  FileCheck2,
  FileText,
  FileWarning,
  FlaskConical,
  FolderKanban,
  PartyPopper,
  ThumbsDown,
  ThumbsUp,
  UserCog,
  UserPlus,
  Wallet,
} from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { PageHeader } from "@/shared/ui/page-header";
import { StatCard } from "@/shared/ui/stat-card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { useAdminDashboard, useApercuActeurs } from "../api";
import { EsgPerformanceSection } from "./EsgPerformanceSection";
import { RecentActivitySection } from "./RecentActivitySection";

/** Vue d'ensemble de l'espace Administrateur (/admin) : synthèse globale, actions prioritaires,
 * performance ESG, statistiques par acteur (5 onglets) et aperçu de l'activité récente. Deux
 * appels réseau distincts — useAdminDashboard (TableauDeBordAdmin, la synthèse déjà en place) et
 * useApercuActeurs (app/admin/apercu.py, statistiques Auditeur/Investisseur/Chercheur/
 * Institution) — jamais fusionnés en un seul gros payload, chacun sert un usage différent
 * (TableauDeBordAdmin reste utilisé seul par ailleurs). Pas de section "accès rapides" séparée :
 * la sidebar (roleNav.ts) donne déjà accès aux espaces principaux. */
export function AdminDashboardPage() {
  const { data, dataUpdatedAt } = useAdminDashboard();
  const { data: apercu } = useApercuActeurs();
  const aucuneActionPrioritaire =
    data !== undefined &&
    data.reports_to_assign === 0 &&
    data.pending_decisions === 0 &&
    data.republication_requests === 0 &&
    data.pending_users === 0 &&
    data.failed_extraction_reports === 0 &&
    data.orphan_reports === 0 &&
    data.overdue_audits === 0;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Tableau de bord"
        description={
          dataUpdatedAt
            ? `Vue d'ensemble de la plateforme — actualisé à ${new Date(dataUpdatedAt).toLocaleTimeString("fr-FR")}.`
            : "Vue d'ensemble de la plateforme et des files de travail nécessitant une intervention."
        }
      />

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

      <section className="space-y-3" aria-label="Actions prioritaires">
        <h2 className="text-base font-semibold text-brand-blue">Actions prioritaires</h2>
        {aucuneActionPrioritaire ? (
          <EmptyState icon={PartyPopper} message="Rien à traiter pour l'instant." />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <ActionCard
              to="/admin/rapports?onglet=a-affecter"
              label="Rapports à affecter"
              count={data?.reports_to_assign}
              icon={<ClipboardCheck className="size-5" />}
            />
            <ActionCard
              to="/admin/rapports?onglet=en-validation"
              label="Décisions à rendre"
              count={data?.pending_decisions}
              icon={<FileCheck2 className="size-5" />}
            />
            <ActionCard
              to="/admin/entreprises?onglet=a-republier"
              label="Demandes de republication"
              count={data?.republication_requests}
              icon={<Building2 className="size-5" />}
            />
            <ActionCard
              to="/admin/utilisateurs#en-attente"
              label="Utilisateurs en attente"
              count={data?.pending_users}
              icon={<UserCog className="size-5" />}
            />
            <ActionCard
              to="/admin/rapports?onglet=alertes"
              label="Extractions en échec"
              count={data?.failed_extraction_reports}
              icon={<AlertTriangle className="size-5" />}
            />
            <ActionCard
              to="/admin/rapports?onglet=alertes"
              label="Rapports orphelins (sans avis)"
              count={data?.orphan_reports}
              icon={<AlertTriangle className="size-5" />}
            />
            <ActionCard
              to="/admin/rapports?onglet=alertes"
              label="Audits en retard"
              count={data?.overdue_audits}
              icon={<FileWarning className="size-5" />}
            />
          </div>
        )}
      </section>

      <section className="space-y-3" aria-label="Performance ESG">
        <h2 className="text-base font-semibold text-brand-blue">Performance ESG</h2>
        <EsgPerformanceSection />
      </section>

      <section className="space-y-3" aria-label="Statistiques par acteur">
        <h2 className="text-base font-semibold text-brand-blue">Statistiques par acteur</h2>
        <Tabs defaultValue="entreprise">
          <TabsList>
            <TabsTrigger value="entreprise">Entreprise</TabsTrigger>
            <TabsTrigger value="auditeur">Auditeur</TabsTrigger>
            <TabsTrigger value="investisseur">Investisseur</TabsTrigger>
            <TabsTrigger value="chercheur">Chercheur</TabsTrigger>
            <TabsTrigger value="institution">Institution</TabsTrigger>
          </TabsList>

          <TabsContent value="entreprise">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
              <StatCard
                label="Demandes de republication"
                value={data?.republication_requests ?? "—"}
                hint="Rapport validé après la dernière publication"
                icon={<Building2 className="size-5" />}
                tone="amber"
                to="/admin/entreprises?onglet=a-republier"
              />
            </div>
          </TabsContent>

          <TabsContent value="auditeur">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
              <StatCard
                label="Audits en retard"
                value={data?.overdue_audits ?? "—"}
                hint="Affecté au-delà du délai attendu"
                icon={<FileWarning className="size-5" />}
                tone="amber"
                to="/admin/rapports?onglet=alertes"
              />
              <StatCard
                label="Avis rendus"
                value={apercu?.auditors.opinions_submitted ?? "—"}
                hint="Total, toutes périodes"
                icon={<FileCheck2 className="size-5" />}
                to="/admin/auditeurs"
              />
            </div>
          </TabsContent>

          <TabsContent value="investisseur">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
              <StatCard
                label="Positions déclarées"
                value={apercu?.investors.declared_positions ?? "—"}
                hint="Montants déclarés par l'Investisseur, non vérifiés"
                icon={<FileText className="size-5" />}
                to="/admin/portefeuilles"
              />
              <StatCard
                label="Entreprises distinctes"
                value={apercu?.investors.distinct_companies ?? "—"}
                hint="Présentes dans au moins un portefeuille"
                icon={<Building2 className="size-5" />}
                to="/admin/portefeuilles"
              />
            </div>
          </TabsContent>

          <TabsContent value="chercheur">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <StatCard
                label="Chercheurs actifs"
                value={data?.active_researchers ?? "—"}
                hint="Comptes rattachables à un projet"
                icon={<FlaskConical className="size-5" />}
                to="/admin/utilisateurs?role=RESEARCHER"
              />
              <StatCard
                label="Affectés à un projet ouvert"
                value={apercu?.researchers.researchers_on_open_projects ?? "—"}
                hint="Chercheurs distincts"
                icon={<FolderKanban className="size-5" />}
                to="/admin/projets?statut=OUVERT"
              />
              <StatCard
                label="Analyses soumises"
                value={apercu?.researchers.submitted_analyses ?? "—"}
                hint="En attente d'examen par l'Institution"
                icon={<FileCheck2 className="size-5" />}
                to="/admin/analyses?statut=SOUMISE"
              />
              <StatCard
                label="Corrections demandées"
                value={apercu?.researchers.analyses_changes_requested ?? "—"}
                hint="Analyses renvoyées au Chercheur"
                icon={<AlertTriangle className="size-5" />}
                tone="amber"
                to="/admin/analyses?statut=CORRECTION_DEMANDEE"
              />
            </div>
          </TabsContent>

          <TabsContent value="institution">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
              <StatCard
                label="Projets clôturés"
                value={apercu?.institutions.closed_projects ?? "—"}
                hint="Terminés"
                icon={<FolderKanban className="size-5" />}
                to="/admin/projets?statut=CLOTURE"
              />
              <StatCard
                label="Invitations en attente"
                value={apercu?.institutions.pending_invitations ?? "—"}
                hint="Chercheur pas encore répondu"
                icon={<UserPlus className="size-5" />}
              />
              <StatCard
                label="Analyses à examiner"
                value={apercu?.institutions.analyses_to_review ?? "—"}
                hint="Soumises, décision en attente"
                icon={<FileCheck2 className="size-5" />}
                to="/admin/analyses?statut=SOUMISE"
              />
            </div>
          </TabsContent>
        </Tabs>
      </section>

      <RecentActivitySection />
    </div>
  );
}

/** Carte d'action — même langage visuel que StatCard (icône, valeur, survol) mais teintée ambre
 * pour signaler "nécessite une intervention" plutôt qu'un simple indicateur informatif, et avec
 * un chevron qui renforce l'affordance de clic. Repliée quand le compteur est à 0 : une carte
 * vide n'apporte rien, mieux vaut ne jamais l'afficher que l'afficher grisée. */
function ActionCard({
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
      className="block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-green focus-visible:ring-offset-2"
    >
      <Card className="gap-4 border-amber-200 py-5 shadow-none transition-all duration-200 ease-out hover:-translate-y-0.5 hover:border-amber-400 hover:shadow-md">
        <CardContent className="flex items-center justify-between gap-4 px-5">
          <div className="flex items-center gap-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300">
              {icon}
            </span>
            <div>
              <p className="text-sm font-medium text-brand-blue">{label}</p>
              <p className="text-xs text-muted-foreground">À traiter</p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <span className="text-xl font-semibold tabular-nums text-brand-blue">
              {count ?? "—"}
            </span>
            <ChevronRight className="size-4 text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
