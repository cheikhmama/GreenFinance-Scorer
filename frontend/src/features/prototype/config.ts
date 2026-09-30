import type { LucideIcon } from "lucide-react";
import {
  BookOpenCheck,
  BriefcaseBusiness,
  Building2,
  ChartNoAxesCombined,
  CircleUserRound,
  ClipboardCheck,
  Database,
  FileSearch,
  FileText,
  FlaskConical,
  Gauge,
  GitCompareArrows,
  GraduationCap,
  LayoutDashboard,
  SlidersHorizontal,
  Users,
} from "lucide-react";
import type { PrototypeRole, RoleSlug } from "./types";

export interface PrototypeNavItem {
  section: string;
  label: string;
  icon: LucideIcon;
}

interface PrototypeRoleConfig {
  slug: RoleSlug;
  role: PrototypeRole;
  label: string;
  persona: string;
  organization: string;
  navigation: PrototypeNavItem[];
}

export const prototypeRoleConfigs: Record<RoleSlug, PrototypeRoleConfig> = {
  admin: {
    slug: "admin",
    role: "ADMIN",
    label: "Administrateur",
    persona: "Aminata Diallo",
    organization: "GreenFinance-Scorer",
    navigation: [
      { section: "dashboard", label: "Tableau de bord", icon: LayoutDashboard },
      { section: "users", label: "Utilisateurs", icon: Users },
      { section: "companies", label: "Entreprises", icon: Building2 },
      { section: "reports", label: "Rapports", icon: FileText },
      { section: "methodology", label: "Méthodologie ESG", icon: SlidersHorizontal },
    ],
  },
  company: {
    slug: "company",
    role: "ENTERPRISE",
    label: "Entreprise",
    persona: "Sofia Martin",
    organization: "Microsoft",
    navigation: [
      { section: "dashboard", label: "Tableau de bord", icon: LayoutDashboard },
      { section: "reports", label: "Rapports", icon: FileText },
      { section: "results", label: "Résultats ESG", icon: Gauge },
      { section: "profile", label: "Profil", icon: CircleUserRound },
    ],
  },
  audit: {
    slug: "audit",
    role: "AUDITOR",
    label: "Auditeur",
    persona: "Lucas Bernard",
    organization: "Audit Climat Conseil",
    navigation: [
      { section: "dashboard", label: "Tableau de bord", icon: LayoutDashboard },
      { section: "assignments", label: "Dossiers affectés", icon: ClipboardCheck },
      { section: "history", label: "Historique", icon: BookOpenCheck },
    ],
  },
  investor: {
    slug: "investor",
    role: "INVESTOR",
    label: "Investisseur",
    persona: "Maya Chen",
    organization: "Impact Capital",
    navigation: [
      { section: "dashboard", label: "Tableau de bord", icon: LayoutDashboard },
      { section: "companies", label: "Entreprises", icon: Building2 },
      { section: "compare", label: "Comparaison", icon: GitCompareArrows },
      { section: "portfolios", label: "Portefeuilles", icon: BriefcaseBusiness },
    ],
  },
  researcher: {
    slug: "researcher",
    role: "RESEARCHER",
    label: "Chercheur",
    persona: "Dr. Noah Kim",
    organization: "Université Verte",
    navigation: [
      { section: "dashboard", label: "Tableau de bord", icon: LayoutDashboard },
      { section: "data", label: "Données", icon: Database },
      { section: "analyses", label: "Analyses", icon: FlaskConical },
      { section: "affiliations", label: "Rattachements", icon: GraduationCap },
    ],
  },
  institution: {
    slug: "institution",
    role: "INSTITUTION",
    label: "Institution",
    persona: "Salma El Idrissi",
    organization: "Institut Climat & Finance",
    navigation: [
      { section: "dashboard", label: "Tableau de bord", icon: LayoutDashboard },
      { section: "companies", label: "Entreprises", icon: FileSearch },
      { section: "researchers", label: "Chercheurs", icon: Users },
      { section: "analyses", label: "Analyses", icon: ChartNoAxesCombined },
    ],
  },
};

export const allRoleConfigs = Object.values(prototypeRoleConfigs);

export function isRoleSlug(value: string | undefined): value is RoleSlug {
  return Boolean(value && value in prototypeRoleConfigs);
}

export const sectionDescriptions: Record<string, string> = {
  dashboard: "Vue d’ensemble et actions prioritaires",
  users: "Création, invitation et prévisualisation des comptes",
  companies: "Données, scores et informations des entreprises",
  reports: "Cycle de dépôt, audit, validation et publication",
  methodology: "Pondérations transparentes du score ESG",
  results: "Scores, émissions et preuves traçables",
  profile: "Identité et informations de l’organisation",
  assignments: "Contrôle des indicateurs et avis d’audit",
  history: "Dossiers contrôlés et décisions finales",
  compare: "Comparaison homogène des performances ESG",
  portfolios: "Positions, score agrégé et empreinte financée",
  data: "Jeux de données ESG autorisés et sourcés",
  analyses: "Études, résultats et exports",
  affiliations: "Collaborations avec les institutions",
  researchers: "Invitations et rattachements des chercheurs",
};
