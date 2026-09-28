import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ApiError } from "@/shared/api/errors";
import {
  getCompanyReport,
  getMyCompanyProfile,
  listCompanyReports,
  submitCompanyReport,
  submitCompanyReportCorrection,
} from "@/shared/api/generated/company/company";
import type {
  BodySubmitCompanyReport,
  BodySubmitCompanyReportCorrection,
  EntreprisePublic,
  RapportESGDetail,
  RapportESGPublic,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

const REPORTS_QUERY_KEY = ["company", "rapports"] as const;
const reportQueryKey = (rapportId: string) => ["company", "rapports", rapportId] as const;

/** GET /company/rapports — la liste des rapports de l'entreprise connectée. */
export function useCompanyReports() {
  return useQuery<RapportESGPublic[], ApiError>({
    queryKey: REPORTS_QUERY_KEY,
    queryFn: () => listCompanyReports(),
  });
}

/** GET /company/rapports/{id} — détail, indicateurs et données carbone inclus. */
export function useCompanyReport(rapportId: string) {
  return useQuery<RapportESGDetail, ApiError>({
    queryKey: reportQueryKey(rapportId),
    queryFn: () => getCompanyReport(rapportId),
    enabled: rapportId.length > 0,
  });
}

/** GET /company/profil — la fiche entreprise telle que vue par les investisseurs, en lecture
 * seule (l'édition reste réservée à l'Admin, voir ARCHITECTURE.md gouvernance Phase 0). */
export function useMyCompanyProfile() {
  return useQuery<EntreprisePublic, ApiError>({
    queryKey: ["company", "profil"],
    queryFn: () => getMyCompanyProfile(),
  });
}

/** POST /company/rapports. Invalide la liste pour que le nouveau dépôt apparaisse aussitôt. */
export function useSubmitReport() {
  const queryClient = useQueryClient();

  return useMutation<RapportESGPublic, ApiError, BodySubmitCompanyReport>({
    mutationFn: (payload) => submitCompanyReport(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: REPORTS_QUERY_KEY });
    },
  });
}

/** POST /company/rapports/{id}/corrections — nouvelle version liée, le rapport d'origine n'est
 * jamais modifié (voir app/company/rapports.py::creer_correction). */
export function useSubmitCorrection(rapportId: string) {
  const queryClient = useQueryClient();

  return useMutation<RapportESGPublic, ApiError, BodySubmitCompanyReportCorrection>({
    mutationFn: (payload) => submitCompanyReportCorrection(rapportId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: REPORTS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: reportQueryKey(rapportId) });
    },
  });
}
