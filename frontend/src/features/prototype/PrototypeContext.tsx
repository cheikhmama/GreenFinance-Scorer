import { createContext, type ReactNode, useContext, useState } from "react";
import { createInitialPrototypeState } from "./data";
import type {
  AccountStatus,
  AffiliationStatus,
  CreateCompanyInput,
  CreateReportInput,
  CreateUserInput,
  Methodology,
  PrototypeAnalysis,
  PrototypeCompany,
  PrototypeReport,
  PrototypeState,
  PrototypeUser,
} from "./types";

interface PrototypeContextValue extends PrototypeState {
  toast: string | null;
  previewUserId: string | null;
  previewCompanyId: string | null;
  createUser: (input: CreateUserInput) => PrototypeUser;
  createCompany: (input: CreateCompanyInput) => PrototypeCompany;
  setUserStatus: (id: string, status: AccountStatus) => void;
  createReport: (input: CreateReportInput) => PrototypeReport;
  updateReport: (id: string, changes: Partial<PrototypeReport>, message: string) => void;
  addPosition: (companyId: string, amount?: number) => void;
  updateAffiliation: (id: string, status: AffiliationStatus) => void;
  inviteResearcher: (researcher: PrototypeUser, institution?: string) => void;
  createAnalysis: (analysis: Omit<PrototypeAnalysis, "id" | "updatedAt">) => void;
  updateMethodology: (methodology: Methodology) => void;
  showToast: (message: string) => void;
  selectPreviewUser: (userId: string | null) => void;
  selectPreviewCompany: (companyId: string | null) => void;
  resetDemo: () => void;
}

const PrototypeContext = createContext<PrototypeContextValue | null>(null);

export function PrototypeProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PrototypeState>(createInitialPrototypeState);
  const [toast, setToast] = useState<string | null>(null);
  const [previewUserId, setPreviewUserId] = useState<string | null>(null);
  const [previewCompanyId, setPreviewCompanyId] = useState<string | null>(null);

  function showToast(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(null), 3500);
  }

  function createUser(input: CreateUserInput) {
    const user: PrototypeUser = {
      ...input,
      id: `usr-${Date.now()}`,
      status: "INVITE",
      lastSeen: "Invitation envoyée à l’instant",
    };
    setState((current) => ({ ...current, users: [user, ...current.users] }));
    showToast(`Compte de ${input.name} créé et invitation simulée.`);
    return user;
  }

  function createCompany(input: CreateCompanyInput) {
    const company: PrototypeCompany = {
      ...input,
      id: `cmp-${Date.now()}`,
      score: 0,
      environmental: 0,
      social: 0,
      governance: 0,
      scope1: 0,
      scope2: 0,
      scope3: 0,
      quality: "À confirmer",
      published: false,
    };
    setState((current) => ({ ...current, companies: [company, ...current.companies] }));
    showToast(`${input.name} ajoutée aux entreprises de démonstration.`);
    return company;
  }

  function setUserStatus(id: string, status: AccountStatus) {
    setState((current) => ({
      ...current,
      users: current.users.map((user) => (user.id === id ? { ...user, status } : user)),
    }));
    showToast("Statut du compte mis à jour.");
  }

  function createReport(input: CreateReportInput) {
    const report: PrototypeReport = {
      ...input,
      id: `rep-${Date.now()}`,
      status: "SOUMIS",
      auditor: null,
      completeness: 0,
      updatedAt: "À l’instant",
      opinion: null,
      correctionNote: null,
      evidencePage: 1,
    };
    setState((current) => ({ ...current, reports: [report, ...current.reports] }));
    showToast("Rapport soumis. Il est maintenant visible par l’administrateur.");
    return report;
  }

  function updateReport(id: string, changes: Partial<PrototypeReport>, message: string) {
    setState((current) => ({
      ...current,
      reports: current.reports.map((report) =>
        report.id === id ? { ...report, ...changes, updatedAt: "À l’instant" } : report,
      ),
      companies:
        changes.status === "PUBLIE"
          ? current.companies.map((company) => {
              const report = current.reports.find((item) => item.id === id);
              return report?.companyId === company.id ? { ...company, published: true } : company;
            })
          : current.companies,
    }));
    showToast(message);
  }

  function addPosition(companyId: string, amount = 100_000) {
    setState((current) => {
      const company = current.companies.find((item) => item.id === companyId);
      if (!company) return current;
      const existing = current.positions.find((position) => position.companyId === companyId);
      if (existing) {
        return {
          ...current,
          positions: current.positions.map((position) =>
            position.id === existing.id
              ? { ...position, amount: position.amount + amount }
              : position,
          ),
        };
      }
      return {
        ...current,
        positions: [
          ...current.positions,
          {
            id: `pos-${Date.now()}`,
            companyId,
            company: company.name,
            amount,
            currency: "EUR",
          },
        ],
      };
    });
    showToast("Position ajoutée au portefeuille principal.");
  }

  function updateAffiliation(id: string, status: AffiliationStatus) {
    setState((current) => ({
      ...current,
      affiliations: current.affiliations.map((affiliation) =>
        affiliation.id === id ? { ...affiliation, status } : affiliation,
      ),
    }));
    showToast("Rattachement mis à jour dans les deux espaces.");
  }

  function inviteResearcher(researcher: PrototypeUser, institution = "Institut Climat & Finance") {
    setState((current) => ({
      ...current,
      affiliations: [
        {
          id: `aff-${Date.now()}`,
          institution,
          researcher: researcher.name,
          researcherEmail: researcher.email,
          status: "INVITE",
          primary: false,
        },
        ...current.affiliations,
      ],
    }));
    showToast("Invitation simulée. Elle est visible dans l’espace Chercheur.");
  }

  function createAnalysis(analysis: Omit<PrototypeAnalysis, "id" | "updatedAt">) {
    setState((current) => ({
      ...current,
      analyses: [
        { ...analysis, id: `ana-${Date.now()}`, updatedAt: "À l’instant" },
        ...current.analyses,
      ],
    }));
    showToast("Analyse créée et synchronisée avec son propriétaire.");
  }

  function updateMethodology(methodology: Methodology) {
    setState((current) => ({ ...current, methodology }));
    showToast(`Méthodologie ${methodology.version} enregistrée.`);
  }

  function resetDemo() {
    setState(createInitialPrototypeState());
    setPreviewUserId(null);
    setPreviewCompanyId(null);
    showToast("Données de démonstration réinitialisées.");
  }

  const value = {
    ...state,
    toast,
    previewUserId,
    previewCompanyId,
    createUser,
    createCompany,
    setUserStatus,
    createReport,
    updateReport,
    addPosition,
    updateAffiliation,
    inviteResearcher,
    createAnalysis,
    updateMethodology,
    showToast,
    selectPreviewUser: setPreviewUserId,
    selectPreviewCompany: setPreviewCompanyId,
    resetDemo,
  };

  return <PrototypeContext.Provider value={value}>{children}</PrototypeContext.Provider>;
}

export function usePrototype() {
  const context = useContext(PrototypeContext);
  if (!context) throw new Error("usePrototype doit être utilisé dans PrototypeProvider");
  return context;
}
