import type {
  AccessRequestStatus,
  InvestorType,
  ResearchDomain,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

/** Libellés des demandes d'accès Investisseur / Chercheur (tâche 5.10). */
export const LIBELLES_TYPE_INVESTISSEUR: Record<InvestorType, string> = {
  INVESTMENT_FUND: "Fonds d’investissement",
  BANK_INSTITUTIONAL: "Banque / Institutionnel",
  BUSINESS_ANGEL: "Business Angel",
  OTHER: "Autre",
};

export const LIBELLES_DOMAINE_RECHERCHE: Record<ResearchDomain, string> = {
  SUSTAINABLE_FINANCE: "Finance durable",
  CARBON_FOOTPRINT: "Empreinte carbone",
  GOVERNANCE: "Gouvernance",
  OTHER: "Autre",
};

export const LIBELLES_STATUT_DEMANDE: Record<AccessRequestStatus, string> = {
  PENDING_APPROVAL: "En attente",
  APPROVED: "Approuvée",
  REJECTED: "Refusée",
};
