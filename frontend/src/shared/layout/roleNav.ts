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
  Settings,
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
  /** Intertitre affiché avant le premier lien d'un groupe (ex. « Supervision »). */
  groupe?: string;
}

export interface RoleNavConfig {
  label: string;
  items: NavItem[];
  /** Route du Profil de ce rôle — rendue à part, fixée en bas de la sidebar (voir
   * AppShell.tsx), jamais mélangée aux `items` : le Profil n'est pas une page métier de
   * l'espace comme les autres, c'est le compte de la personne connectée. */
  profilTo: string;
  /** Le Profil est déjà un lien de `items` : pas de carte Profil en bas de la sidebar
   * (espace Entreprise, tâche 5.9). */
  profilDansNavigation?: boolean;
}

/** Navigation réelle par rôle. */
export const roleNavConfig: Record<Role, RoleNavConfig> = {
  [Role.ADMIN]: {
    label: "Administrateur",
    profilTo: "/admin/profil",
    items: [
      { to: "/admin", label: "Tableau de bord", icon: LayoutDashboard, end: true },
      { to: "/admin/utilisateurs", label: "Utilisateurs", icon: Users },
      { to: "/admin/entreprises", label: "Entreprises", icon: Building2 },
      { to: "/admin/rapports", label: "Rapports", icon: FileText },
      { to: "/admin/journal-audit", label: "Journal d'audit", icon: History },
      // Pages de suivi déjà atteignables depuis le tableau de bord, jusqu'ici absentes du menu.
      { to: "/admin/auditeurs", label: "Auditeurs", icon: ClipboardCheck, groupe: "Supervision" },
      { to: "/admin/portefeuilles", label: "Portefeuilles", icon: Wallet, groupe: "Supervision" },
      { to: "/admin/projets", label: "Projets", icon: FolderKanban, groupe: "Supervision" },
      { to: "/admin/analyses", label: "Analyses", icon: FlaskConical, groupe: "Supervision" },
    ],
  },
  [Role.ENTERPRISE]: {
    label: "Entreprise",
    profilTo: "/company/profile",
    // Trois liens de structure seulement (tâche 5.9) : l'action « Nouvelle déclaration » vit
    // dans l'en-tête de « Mes déclarations », jamais en double dans la sidebar.
    profilDansNavigation: true,
    items: [
      { to: "/company", label: "Tableau de bord", icon: LayoutDashboard, end: true },
      { to: "/company/declarations", label: "Mes déclarations", icon: FileText },
      { to: "/company/profile", label: "Profil entreprise", icon: Settings },
    ],
  },
  [Role.AUDITOR]: {
    label: "Auditeur",
    profilTo: "/audit/profil",
    items: [
      { to: "/audit", label: "Dossiers affectés", icon: ClipboardCheck, end: true },
      { to: "/audit/historique", label: "Historique", icon: BookOpenCheck },
    ],
  },
  [Role.INVESTOR]: {
    label: "Investisseur",
    profilTo: "/investor/profil",
    items: [
      { to: "/investor", label: "Tableau de bord", icon: LayoutDashboard, end: true },
      { to: "/investor/entreprises", label: "Entreprises", icon: Building2 },
      { to: "/investor/comparaison", label: "Comparaison", icon: Scale },
      { to: "/investor/portefeuilles", label: "Portefeuilles", icon: Wallet },
    ],
  },
  [Role.RESEARCHER]: {
    label: "Chercheur",
    profilTo: "/researcher/profil",
    items: [
      { to: "/researcher", label: "Tableau de bord", icon: LayoutDashboard, end: true },
      { to: "/researcher/entreprises", label: "Données", icon: Building2 },
      { to: "/researcher/projets", label: "Mes projets", icon: FolderKanban },
      { to: "/researcher/analyses", label: "Analyses", icon: FlaskConical },
      { to: "/researcher/validation-croisee", label: "Validation croisée", icon: Scale },
      { to: "/researcher/rattachements", label: "Rattachements", icon: UserPlus },
    ],
  },
  [Role.INSTITUTION]: {
    label: "Institution",
    profilTo: "/institution/profil",
    items: [
      { to: "/institution", label: "Tableau de bord", icon: LayoutDashboard, end: true },
      { to: "/institution/entreprises", label: "Entreprises", icon: Building2 },
      { to: "/institution/chercheurs", label: "Chercheurs", icon: Briefcase },
      { to: "/institution/projets", label: "Projets", icon: FolderKanban },
      { to: "/institution/analyses", label: "Analyses", icon: FlaskConical },
    ],
  },
};
