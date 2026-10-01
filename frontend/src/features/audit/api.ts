import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ApiError } from "@/shared/api/errors";
import {
  getAssignedReport,
  getAuditPreScore,
  listAssignedReports,
  listAuditReviews,
  listMyAuditOpinions,
  reviewReportValue,
  submitAuditOpinion,
} from "@/shared/api/generated/audit/audit";
import type {
  AvisAuditAdmin,
  MetricReviewEntry,
  MetricReviewRequest,
  PreScore,
  RapportESGDetail,
  RapportESGPublic,
  SoumettreAvisRequest,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

const DOSSIERS_QUERY_KEY = ["audit", "rapports"] as const;
const dossierQueryKey = (rapportId: string) => ["audit", "rapports", rapportId] as const;
const HISTORIQUE_QUERY_KEY = ["audit", "historique"] as const;
const revuesQueryKey = (rapportId: string) => ["audit", "rapports", rapportId, "reviews"] as const;
const preScoreQueryKey = (rapportId: string) =>
  ["audit", "rapports", rapportId, "pre-score"] as const;

/** GET /audit/rapports — dossiers affectés, en attente d'avis. */
export function useAssignedReports() {
  return useQuery<RapportESGPublic[], ApiError>({
    queryKey: DOSSIERS_QUERY_KEY,
    queryFn: () => listAssignedReports(),
  });
}

/** GET /audit/rapports/{id} — reste accessible après avis rendu (pas de restriction de statut). */
export function useAssignedReport(rapportId: string) {
  return useQuery<RapportESGDetail, ApiError>({
    queryKey: dossierQueryKey(rapportId),
    queryFn: () => getAssignedReport(rapportId),
    enabled: rapportId.length > 0,
  });
}

/** GET /audit/historique — tous les avis déjà rendus par l'auditeur connecté. */
export function useAuditHistory() {
  return useQuery<AvisAuditAdmin[], ApiError>({
    queryKey: HISTORIQUE_QUERY_KEY,
    queryFn: () => listMyAuditOpinions(),
  });
}

/** POST /audit/rapports/{id}/avis — fait passer le rapport en PENDING_DECISION côté serveur. */
export function useSubmitOpinion(rapportId: string) {
  const queryClient = useQueryClient();

  return useMutation<AvisAuditAdmin, ApiError, SoumettreAvisRequest>({
    mutationFn: (payload) => submitAuditOpinion(rapportId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DOSSIERS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: dossierQueryKey(rapportId) });
      queryClient.invalidateQueries({ queryKey: HISTORIQUE_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: preScoreQueryKey(rapportId) });
    },
  });
}

/** GET /audit/rapports/{id}/reviews (tâche 5.6) — journal des décisions, plus ancienne d'abord. */
export function useAuditReviews(rapportId: string) {
  return useQuery<MetricReviewEntry[], ApiError>({
    queryKey: revuesQueryKey(rapportId),
    queryFn: () => listAuditReviews(rapportId),
    enabled: rapportId.length > 0,
  });
}

/** POST /audit/rapports/{id}/reviews — l'état de la valeur change : dossier et journal relus. */
export function useReviewValue(rapportId: string) {
  const queryClient = useQueryClient();
  return useMutation<MetricReviewEntry, ApiError, MetricReviewRequest>({
    mutationFn: (payload) => reviewReportValue(rapportId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dossierQueryKey(rapportId) });
      queryClient.invalidateQueries({ queryKey: revuesQueryKey(rapportId) });
    },
  });
}

/** GET /audit/rapports/{id}/pre-score — demandé seulement une fois l'avis rendu (409 avant). */
export function useAuditPreScore(rapportId: string, enabled: boolean) {
  return useQuery<PreScore, ApiError>({
    queryKey: preScoreQueryKey(rapportId),
    queryFn: () => getAuditPreScore(rapportId),
    enabled,
    retry: false,
  });
}
