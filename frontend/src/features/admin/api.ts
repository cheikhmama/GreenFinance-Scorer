import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ApiError } from "@/shared/api/errors";
import {
  assignReportAuditor,
  changeUserRole,
  createUser,
  deactivateUser,
  getAdminDashboard,
  getAdminReport,
  listAdminCompanyReports,
  listAllCompanies,
  listAuditLog,
  listPublishableCompanies,
  listReportOpinions,
  listReportsInValidation,
  listReportsToAssign,
  listReportVersions,
  listUsersByRole,
  publishCompany,
  reactivateCompany,
  reactivateUser,
  rejectReport,
  requestReportCorrection,
  suspendCompany,
  validateReport,
} from "@/shared/api/generated/admin/admin";
import type {
  AffecterAuditeurRequest,
  AvisAuditAdmin,
  ChangerRoleRequest,
  CreerUtilisateurRequest,
  DecisionAdminRequest,
  EntreprisePublic,
  ListAuditLogParams,
  PageEntrepriseAdmin,
  PageEntreprisePublic,
  PageJournalAuditPublic,
  PageUtilisateurPublic,
  RapportESGDetail,
  RapportESGPublic,
  Role,
  TableauDeBordAdmin,
  UtilisateurCree,
  UtilisateurPublic,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

// Chargement initial de 3 éléments, puis +3 par clic sur "Voir plus", jusqu'à épuisement réel de
// la liste côté serveur (voir UsersSection / PublishableCompaniesSection).
export const TAILLE_PAGE_ADMIN = 3;

const A_AFFECTER_KEY = ["admin", "rapports", "a-affecter"] as const;
const EN_VALIDATION_KEY = ["admin", "rapports", "en-validation"] as const;
const rapportKey = (rapportId: string) => ["admin", "rapports", rapportId] as const;
const avisKey = (rapportId: string) => ["admin", "rapports", rapportId, "avis"] as const;
const PUBLIABLES_KEY = ["admin", "entreprises", "publiables"] as const;
const TOUTES_ENTREPRISES_KEY = ["admin", "entreprises", "toutes"] as const;
const utilisateursKey = (role: Role) => ["admin", "utilisateurs", role] as const;
const versionsKey = (rapportId: string) => ["admin", "rapports", rapportId, "versions"] as const;
const JOURNAL_AUDIT_KEY = ["admin", "journal-audit"] as const;
const companyReportsKey = (entrepriseId: string) =>
  ["admin", "entreprises", entrepriseId, "rapports"] as const;

function pageSuivante<T extends { page: number; pages: number }>(dernierePage: T): number | undefined {
  return dernierePage.page < dernierePage.pages ? dernierePage.page + 1 : undefined;
}

function invalidateFileDattente(queryClient: ReturnType<typeof useQueryClient>, rapportId: string) {
  queryClient.invalidateQueries({ queryKey: A_AFFECTER_KEY });
  queryClient.invalidateQueries({ queryKey: EN_VALIDATION_KEY });
  queryClient.invalidateQueries({ queryKey: rapportKey(rapportId) });
}

export function useAdminDashboard() {
  return useQuery<TableauDeBordAdmin, ApiError>({
    queryKey: ["admin", "dashboard"] as const,
    queryFn: () => getAdminDashboard(),
  });
}

export function useReportsToAssign() {
  return useQuery<RapportESGPublic[], ApiError>({
    queryKey: A_AFFECTER_KEY,
    queryFn: () => listReportsToAssign(),
  });
}

export function useReportsInValidation() {
  return useQuery<RapportESGPublic[], ApiError>({
    queryKey: EN_VALIDATION_KEY,
    queryFn: () => listReportsInValidation(),
  });
}

export function useAdminReport(rapportId: string) {
  return useQuery<RapportESGDetail, ApiError>({
    queryKey: rapportKey(rapportId),
    queryFn: () => getAdminReport(rapportId),
    enabled: rapportId.length > 0,
  });
}

export function useReportOpinions(rapportId: string) {
  return useQuery<AvisAuditAdmin[], ApiError>({
    queryKey: avisKey(rapportId),
    queryFn: () => listReportOpinions(rapportId),
    enabled: rapportId.length > 0,
  });
}

export function useReportVersions(rapportId: string) {
  return useQuery<RapportESGPublic[], ApiError>({
    queryKey: versionsKey(rapportId),
    queryFn: () => listReportVersions(rapportId),
    enabled: rapportId.length > 0,
  });
}

export function useAssignReport(rapportId: string) {
  const queryClient = useQueryClient();
  return useMutation<RapportESGPublic, ApiError, AffecterAuditeurRequest>({
    mutationFn: (payload) => assignReportAuditor(rapportId, payload),
    onSuccess: () => invalidateFileDattente(queryClient, rapportId),
  });
}

export function useValidateReport(rapportId: string) {
  const queryClient = useQueryClient();
  return useMutation<RapportESGPublic, ApiError, DecisionAdminRequest>({
    mutationFn: (payload) => validateReport(rapportId, payload),
    onSuccess: () => {
      invalidateFileDattente(queryClient, rapportId);
      queryClient.invalidateQueries({ queryKey: PUBLIABLES_KEY });
    },
  });
}

export function useRejectReport(rapportId: string) {
  const queryClient = useQueryClient();
  return useMutation<RapportESGPublic, ApiError, DecisionAdminRequest>({
    mutationFn: (payload) => rejectReport(rapportId, payload),
    onSuccess: () => invalidateFileDattente(queryClient, rapportId),
  });
}

export function useRequestReportCorrection(rapportId: string) {
  const queryClient = useQueryClient();
  return useMutation<RapportESGPublic, ApiError, DecisionAdminRequest>({
    mutationFn: (payload) => requestReportCorrection(rapportId, payload),
    onSuccess: () => invalidateFileDattente(queryClient, rapportId),
  });
}

export function usePublishableCompanies(recherche = "") {
  return useInfiniteQuery<PageEntreprisePublic, ApiError>({
    queryKey: [...PUBLIABLES_KEY, recherche],
    queryFn: ({ pageParam }) =>
      listPublishableCompanies({
        recherche: recherche || undefined,
        page: pageParam as number,
        page_size: TAILLE_PAGE_ADMIN,
      }),
    initialPageParam: 1,
    getNextPageParam: pageSuivante,
  });
}

/** GET /admin/entreprises — contrairement à usePublishableCompanies, remonte TOUTE entreprise
 * (y compris sans rapport, sans compte utilisateur rattaché) avec un résumé de statut : vue de
 * suivi pour l'Administrateur, pas un sélecteur d'action de publication. */
export function useAllCompanies(recherche = "") {
  return useInfiniteQuery<PageEntrepriseAdmin, ApiError>({
    queryKey: [...TOUTES_ENTREPRISES_KEY, recherche],
    queryFn: ({ pageParam }) =>
      listAllCompanies({
        recherche: recherche || undefined,
        page: pageParam as number,
        page_size: TAILLE_PAGE_ADMIN,
      }),
    initialPageParam: 1,
    getNextPageParam: pageSuivante,
  });
}

export function usePublishCompany() {
  const queryClient = useQueryClient();
  return useMutation<EntreprisePublic, ApiError, string>({
    mutationFn: (entrepriseId) => publishCompany(entrepriseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PUBLIABLES_KEY });
    },
  });
}

export function useSuspendCompany() {
  const queryClient = useQueryClient();
  return useMutation<EntreprisePublic, ApiError, string>({
    mutationFn: (entrepriseId) => suspendCompany(entrepriseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TOUTES_ENTREPRISES_KEY });
    },
  });
}

export function useReactivateCompany() {
  const queryClient = useQueryClient();
  return useMutation<EntreprisePublic, ApiError, string>({
    mutationFn: (entrepriseId) => reactivateCompany(entrepriseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TOUTES_ENTREPRISES_KEY });
    },
  });
}

export function useCompanyReports(entrepriseId: string) {
  return useQuery<RapportESGPublic[], ApiError>({
    queryKey: companyReportsKey(entrepriseId),
    queryFn: () => listAdminCompanyReports(entrepriseId),
    enabled: entrepriseId.length > 0,
  });
}

// Pour un sélecteur (ex. affecter un auditeur à un rapport), pas pour une liste parcourue par
// l'administrateur : une seule page, à la taille maximale acceptée par l'API — jamais la
// pagination "3 puis +3 par clic" ci-dessus, qui viderait le sélecteur au-delà des 3 premiers
// comptes et empêcherait de choisir les autres.
export function useUtilisateursSelectionnables(role: Role) {
  return useQuery<UtilisateurPublic[], ApiError>({
    queryKey: [...utilisateursKey(role), "selectionnable"],
    queryFn: async () => {
      const page = await listUsersByRole({ role, page: 1, page_size: 50 });
      return page.items;
    },
  });
}

export function useUsersByRole(
  role: Role,
  recherche = "",
  inclureInactifs = false,
  enAttente = false,
) {
  return useInfiniteQuery<PageUtilisateurPublic, ApiError>({
    queryKey: [...utilisateursKey(role), recherche, inclureInactifs, enAttente],
    queryFn: ({ pageParam }) =>
      listUsersByRole({
        role,
        recherche: recherche || undefined,
        inclure_inactifs: inclureInactifs,
        doit_changer_mot_de_passe: enAttente || undefined,
        page: pageParam as number,
        page_size: TAILLE_PAGE_ADMIN,
      }),
    initialPageParam: 1,
    getNextPageParam: pageSuivante,
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation<UtilisateurCree, ApiError, CreerUtilisateurRequest>({
    mutationFn: (payload) => createUser(payload),
    onSuccess: (utilisateur) => {
      queryClient.invalidateQueries({ queryKey: utilisateursKey(utilisateur.role) });
    },
  });
}

export function useDeactivateUser(role: Role) {
  const queryClient = useQueryClient();
  return useMutation<UtilisateurPublic, ApiError, string>({
    mutationFn: (utilisateurId) => deactivateUser(utilisateurId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: utilisateursKey(role) });
    },
  });
}

export function useReactivateUser(role: Role) {
  const queryClient = useQueryClient();
  return useMutation<UtilisateurPublic, ApiError, string>({
    mutationFn: (utilisateurId) => reactivateUser(utilisateurId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: utilisateursKey(role) });
    },
  });
}

export interface FiltresJournalAudit {
  action?: string;
  type_ressource?: string;
  concerne_id?: string;
}

const TAILLE_PAGE_JOURNAL = 20;

export function useJournalAudit(filtres: FiltresJournalAudit = {}) {
  return useInfiniteQuery<PageJournalAuditPublic, ApiError>({
    queryKey: [...JOURNAL_AUDIT_KEY, filtres],
    queryFn: ({ pageParam }) =>
      listAuditLog({
        ...filtres,
        page: pageParam as number,
        page_size: TAILLE_PAGE_JOURNAL,
      } satisfies ListAuditLogParams),
    initialPageParam: 1,
    getNextPageParam: pageSuivante,
  });
}

export function useChangeUserRole(currentRole: Role) {
  const queryClient = useQueryClient();
  return useMutation<
    UtilisateurPublic,
    ApiError,
    { utilisateurId: string; payload: ChangerRoleRequest }
  >({
    mutationFn: ({ utilisateurId, payload }) => changeUserRole(utilisateurId, payload),
    onSuccess: (utilisateur) => {
      queryClient.invalidateQueries({ queryKey: utilisateursKey(currentRole) });
      queryClient.invalidateQueries({ queryKey: utilisateursKey(utilisateur.role) });
    },
  });
}
