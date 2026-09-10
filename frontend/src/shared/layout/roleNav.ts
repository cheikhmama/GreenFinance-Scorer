import type { LucideIcon } from "lucide-react";
import {
  BookOpenCheck,
  Briefcase,
  Building2,
  ClipboardCheck,
  FileText,
  FlaskConical,
  FolderKanban,
  History,
  LayoutDashboard,
  Scale,
  UserPlus,
  Users,
  Wallet,
} from "lucide-react";
import { Role } from "@/features/auth/schemas";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Correspond à `end` de NavLink — évite qu'un lien de tableau de bord reste actif
   * quand on est sur une sous-route (ex. /admin/rapports/:id). */
  end?: boolean;
}

export interface RoleNavConfig {
  label: string;
  items: NavItem[];
}

/** Navigation réelle par rôle — un seul élément « Tableau de bord » pour les espaces qui n'ont
 * pas encore de sous-pages dédiées (Entreprise). */
export const roleNavConfig: Record<Role, RoleNavConfig> = {
  [Role.ADMINISTRATEUR]: {
    label: "Administrateur",
    items: [
      { to: "/admin", label: "Tableau de bord", icon: LayoutDashboard, end: true },
      { to: "/admin/utilisateurs", label: "Utilisateurs", icon: Users },
      { to: "/admin/entreprises", label: "Entreprises", icon: Building2 },
      { to: "/admin/rapports", label: "Rapports", icon: FileText },
      { to: "/admin/journal-audit", label: "Journal d'audit", icon: History },
    ],
  },
  [Role.ENTREPRISE]: {
    label: "Entreprise",
    items: [{ to: "/company", label: "Tableau de bord", icon: LayoutDashboard, end: true }],
  },
  [Role.AUDITEUR]: {
    label: "Auditeur",
    items: [
      { to: "/audit", label: "Dossiers affectés", icon: ClipboardCheck, end: true },
      { to: "/audit/historique", label: "Historique", icon: BookOpenCheck },
    ],
  },
  [Role.INVESTISSEUR]: {
    label: "Investisseur",
    items: [
      { to: "/investor", label: "Tableau de bord", icon: LayoutDashboard, end: true },
      { to: "/investor/entreprises", label: "Entreprises publiées", icon: Building2 },
      { to: "/investor/comparaison", label: "Comparaison", icon: Scale },
      { to: "/investor/portefeuilles", label: "Portefeuilles", icon: Wallet },
    ],
  },
  [Role.CHERCHEUR]: {
    label: "Chercheur",
    items: [
      { to: "/researcher", label: "Tableau de bord", icon: LayoutDashboard, end: true },
      { to: "/researcher/entreprises", label: "Données", icon: Building2 },
      { to: "/researcher/analyses", label: "Analyses", icon: FlaskConical },
      { to: "/researcher/rattachements", label: "Rattachements", icon: UserPlus },
    ],
  },
  [Role.INSTITUTION]: {
    label: "Institution",
    items: [
      { to: "/institution", label: "Tableau de bord", icon: LayoutDashboard, end: true },
      { to: "/institution/chercheurs", label: "Chercheurs", icon: Briefcase },
      { to: "/institution/projets", label: "Projets", icon: FolderKanban },
    ],
  },
};
