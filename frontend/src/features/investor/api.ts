import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { downloadFile } from "@/shared/api/download";
import type { ApiError } from "@/shared/api/errors";
import type {
  AjouterPositionRequest,
  BodyImportPortfolioPositions,
  CreerPortefeuilleRequest,
  EntrepriseDetailInvestisseur,
  EntreprisePublieePublic,
  FermerPositionRequest,
  ModifierPositionRequest,
  PageEntreprisePublieePublic,
  PortefeuilleDetail,
  PortefeuilleResume,
  PortfolioCarbon,
  PortfolioImportResult,
  PositionDetail,
  RenommerPortefeuilleRequest,
  TableauDeBordInvestisseur,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  addPosition,
  archivePortfolio,
  closePosition,
  compareCompanies,
  createPortfolio,
  deletePortfolio,
  deletePosition,
  getInvestorDashboard,
  getPortfolioCarbon,
  getPortfolioDetail,
  getPublishedCompanyDetail,
  importPortfolioPositions,
  listMyPortfolios,
  listPublishedCompanies,
  renamePortfolio,
  restorePortfolio,
  updatePosition,
} from "@/shared/api/generated/investor/investor";
import { chargerToutesLesPages, TAILLE_PAGE_TABLE } from "@/shared/api/toutesLesPages";

export const TAILLE_PAGE_INVESTOR = 10;

const ENTREPRISES_KEY = ["investor", "entreprises"] as const;
const entrepriseKey = (id: string) => ["investor", "entreprises", id] as const;
const DASHBOARD_KEY = ["investor", "dashboard"] as const;
const PORTEFEUILLES_KEY = ["investor", "portefeuilles"] as const;
const portefeuilleKey = (id: string) => ["investor", "portefeuilles", id] as const;

function pageSuivante<T extends { page: number; pages: number }>(
  dernierePage: T,
): number | undefined {
  return dernierePage.page < dernierePage.pages ? dernierePage.page + 1 : undefined;
}

export function useInvestorDashboard() {
  return useQuery<TableauDeBordInvestisseur, ApiError>({
    queryKey: DASHBOARD_KEY,
    queryFn: () => getInvestorDashboard(),
  });
}

export function usePublishedCompanies(filtres: {
  secteur?: string;
  pays?: string;
  recherche?: string;
}) {
  return useInfiniteQuery<PageEntreprisePublieePublic, ApiError>({
    queryKey: [...ENTREPRISES_KEY, filtres],
    queryFn: ({ pageParam }) =>
      listPublishedCompanies({
        secteur: filtres.secteur || undefined,
        pays: filtres.pays || undefined,
        recherche: filtres.recherche || undefined,
        page: pageParam as number,
        page_size: TAILLE_PAGE_INVESTOR,
      }),
    initialPageParam: 1,
    getNextPageParam: pageSuivante,
  });
}

/** Toutes les entreprises publiÃ©es, pour la table de donnÃ©es (tÃ¢che 5.18) : recherche, filtres
 * et tri se font ensuite dans le navigateur. */
export function useTableEntreprisesPubliees() {
  return useQuery<EntreprisePublieePublic[], ApiError>({
    queryKey: [...ENTREPRISES_KEY, "table"],
    queryFn: () =>
      chargerToutesLesPages((page) =>
        listPublishedCompanies({ page, page_size: TAILLE_PAGE_TABLE }),
      ),
  });
}

export function useCompanyDetail(entrepriseId: string) {
  return useQuery<EntrepriseDetailInvestisseur, ApiError>({
    queryKey: entrepriseKey(entrepriseId),
    queryFn: () => getPublishedCompanyDetail(entrepriseId),
    enabled: entrepriseId.length > 0,
  });
}

/** GET /investor/comparaison â€” activÃ©e seulement Ã  partir de 2 entreprises sÃ©lectionnÃ©es, une
 * comparaison Ã  une seule entreprise n'a pas de sens. */
export function useCompareCompanies(entrepriseIds: string[]) {
  return useQuery<EntrepriseDetailInvestisseur[], ApiError>({
    queryKey: ["investor", "comparaison", entrepriseIds],
    queryFn: () => compareCompanies({ entreprise_ids: entrepriseIds }),
    enabled: entrepriseIds.length >= 2,
  });
}

/** Tous mes portefeuilles, actifs et archivÃ©s, pour la table de donnÃ©es (tÃ¢che 5.18). La clÃ©
 * est rangÃ©e sous celle des portefeuilles : crÃ©ation, archivage et restauration la rafraÃ®chissent. */
export function useTablePortefeuilles() {
  return useQuery<PortefeuilleResume[], ApiError>({
    queryKey: [...PORTEFEUILLES_KEY, "table"],
    queryFn: () =>
      chargerToutesLesPages((page) => listMyPortfolios({ page, page_size: TAILLE_PAGE_TABLE })),
  });
}

export function usePortfolioDetail(portefeuilleId: string) {
  return useQuery<PortefeuilleDetail, ApiError>({
    queryKey: portefeuilleKey(portefeuilleId),
    queryFn: () => getPortfolioDetail(portefeuilleId),
    enabled: portefeuilleId.length > 0,
  });
}

/** GET /portfolios/{id}/carbon (tÃ¢che 2.3) â€” empreinte PCAF, calculÃ©e Ã  la demande. Sa clÃ© est
 * rangÃ©e sous celle du portefeuille : toute invalidation aprÃ¨s une mutation de position la
 * rafraÃ®chit aussi. */
export function usePortfolioCarbon(portefeuilleId: string) {
  return useQuery<PortfolioCarbon, ApiError>({
    queryKey: [...portefeuilleKey(portefeuilleId), "carbon"],
    queryFn: () => getPortfolioCarbon(portefeuilleId),
    enabled: portefeuilleId.length > 0,
  });
}

/** POST /portfolios/{id}/positions/import (tÃ¢che 2.2) â€” tout ou rien : une 422 porte
 * `fields.line_<n>` / `fields.file`, et rien n'est enregistrÃ©. */
export function useImportPositions(portefeuilleId: string) {
  const queryClient = useQueryClient();
  return useMutation<PortfolioImportResult, ApiError, BodyImportPortfolioPositions>({
    mutationFn: (payload) => importPortfolioPositions(portefeuilleId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: portefeuilleKey(portefeuilleId) });
      queryClient.invalidateQueries({ queryKey: PORTEFEUILLES_KEY });
    },
  });
}

export function useCreatePortfolio() {
  const queryClient = useQueryClient();
  return useMutation<PortefeuilleResume, ApiError, CreerPortefeuilleRequest>({
    mutationFn: (payload) => createPortfolio(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PORTEFEUILLES_KEY });
    },
  });
}

export function useRenamePortfolio(portefeuilleId: string) {
  const queryClient = useQueryClient();
  return useMutation<PortefeuilleResume, ApiError, RenommerPortefeuilleRequest>({
    mutationFn: (payload) => renamePortfolio(portefeuilleId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PORTEFEUILLES_KEY });
      queryClient.invalidateQueries({ queryKey: portefeuilleKey(portefeuilleId) });
    },
  });
}

function useSetPortfolioArchived(portefeuilleId: string, archived: boolean) {
  const queryClient = useQueryClient();
  return useMutation<PortefeuilleResume, ApiError, void>({
    mutationFn: () =>
      archived ? archivePortfolio(portefeuilleId) : restorePortfolio(portefeuilleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PORTEFEUILLES_KEY });
      queryClient.invalidateQueries({ queryKey: portefeuilleKey(portefeuilleId) });
    },
  });
}

export function useArchivePortfolio(portefeuilleId: string) {
  return useSetPortfolioArchived(portefeuilleId, true);
}

export function useRestorePortfolio(portefeuilleId: string) {
  return useSetPortfolioArchived(portefeuilleId, false);
}

export function useDeletePortfolio() {
  const queryClient = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (portefeuilleId) => deletePortfolio(portefeuilleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PORTEFEUILLES_KEY });
    },
  });
}

function invalidatePortfolio(
  queryClient: ReturnType<typeof useQueryClient>,
  portefeuilleId: string,
) {
  queryClient.invalidateQueries({ queryKey: portefeuilleKey(portefeuilleId) });
  queryClient.invalidateQueries({ queryKey: PORTEFEUILLES_KEY });
}

export function useAddPosition(portefeuilleId: string) {
  const queryClient = useQueryClient();
  return useMutation<PositionDetail, ApiError, AjouterPositionRequest>({
    mutationFn: (payload) => addPosition(portefeuilleId, payload),
    onSuccess: () => invalidatePortfolio(queryClient, portefeuilleId),
  });
}

export function useUpdatePosition(portefeuilleId: string) {
  const queryClient = useQueryClient();
  return useMutation<
    PositionDetail,
    ApiError,
    { positionId: string; payload: ModifierPositionRequest }
  >({
    mutationFn: ({ positionId, payload }) => updatePosition(portefeuilleId, positionId, payload),
    onSuccess: () => invalidatePortfolio(queryClient, portefeuilleId),
  });
}

export function useClosePosition(portefeuilleId: string) {
  const queryClient = useQueryClient();
  return useMutation<
    PositionDetail,
    ApiError,
    { positionId: string; payload: FermerPositionRequest }
  >({
    mutationFn: ({ positionId, payload }) => closePosition(portefeuilleId, positionId, payload),
    onSuccess: () => invalidatePortfolio(queryClient, portefeuilleId),
  });
}

export function useDeletePosition(portefeuilleId: string) {
  const queryClient = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (positionId) => deletePosition(portefeuilleId, positionId),
    onSuccess: () => invalidatePortfolio(queryClient, portefeuilleId),
  });
}

/** GET /investor/portefeuilles/{id}/export â€” pas un hook TanStack Query (une action, pas une
 * donnÃ©e mise en cache) : dÃ©clenche un tÃ©lÃ©chargement navigateur rÃ©el du CSV. */
export function exportPortfolioFile(
  portefeuilleId: string,
  nomPortefeuille: string,
): Promise<void> {
  return downloadFile(
    `/investor/portefeuilles/${portefeuilleId}/export`,
    `portefeuille-${nomPortefeuille}.csv`,
  );
}
