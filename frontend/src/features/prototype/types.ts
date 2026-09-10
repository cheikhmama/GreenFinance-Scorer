import type { Role } from "@/features/auth/schemas";

export type PrototypeRole = Role;

export type RoleSlug = "admin" | "company" | "audit" | "investor" | "researcher" | "institution";

export type AccountStatus = "INVITE" | "ACTIF" | "DESACTIVE";

export type ReportStatus =
  | "BROUILLON"
  | "SOUMIS"
  | "A_AFFECTER"
  | "EN_AUDIT"
  | "CORRECTION_DEMANDEE"
  | "CORRECTION_SOUMISE"
  | "VALIDE"
  | "PUBLIE"
  | "REJETE";

export interface PrototypeUser {
  id: string;
  name: string;
  email: string;
  role: PrototypeRole;
  organization: string;
  entityId?: string;
  profile?: Record<string, string>;
  status: AccountStatus;
  lastSeen: string;
}

export interface PrototypeCompany {
  id: string;
  name: string;
  website: string;
  logoUrl: string | null;
  sector: string;
  country: string;
  contact: string;
  score: number;
  environmental: number;
  social: number;
  governance: number;
  scope1: number;
  scope2: number;
  scope3: number;
  quality: "Élevée" | "Moyenne" | "À confirmer";
  published: boolean;
}

export interface PrototypeReport {
  id: string;
  companyId: string;
  company: string;
  title: string;
  year: number;
  status: ReportStatus;
  auditor: string | null;
  completeness: number;
  updatedAt: string;
  opinion: string | null;
  correctionNote: string | null;
  evidencePage: number;
}

export interface PortfolioPosition {
  id: string;
  companyId: string;
  company: string;
  amount: number;
  currency: "EUR" | "USD";
}

export type AffiliationStatus = "INVITE" | "ACTIF" | "SUSPENDU";

export interface Affiliation {
  id: string;
  institution: string;
  researcher: string;
  researcherEmail: string;
  status: AffiliationStatus;
  primary: boolean;
}

export type AnalysisStatus = "BROUILLON" | "TERMINEE" | "EXPORTEE";

export interface PrototypeAnalysis {
  id: string;
  title: string;
  author: string;
  owner: "Personnel" | "Institut Climat & Finance";
  companies: string[];
  period: string;
  status: AnalysisStatus;
  updatedAt: string;
}

export interface Methodology {
  version: string;
  environmental: number;
  social: number;
  governance: number;
  status: "ACTIVE" | "BROUILLON";
}

export interface PrototypeState {
  users: PrototypeUser[];
  companies: PrototypeCompany[];
  reports: PrototypeReport[];
  positions: PortfolioPosition[];
  affiliations: Affiliation[];
  analyses: PrototypeAnalysis[];
  methodology: Methodology;
}

export interface CreateUserInput {
  name: string;
  email: string;
  role: PrototypeRole;
  organization: string;
  entityId?: string;
  profile?: Record<string, string>;
}

export interface CreateCompanyInput {
  name: string;
  website: string;
  logoUrl: string | null;
  sector: string;
  country: string;
  contact: string;
}

export interface CreateReportInput {
  companyId: string;
  company: string;
  title: string;
  year: number;
}
