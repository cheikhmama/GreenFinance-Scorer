import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ApiError } from "@/shared/api/errors";
import {
  getAssignedReport,
  listAssignedReports,
  listMyAuditOpinions,
  submitAuditOpinion,
} from "@/shared/api/generated/audit/audit";
import type {
  AvisAuditAdmin,
  RapportESGDetail,
  RapportESGPublic,
  SoumettreAvisRequest,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

const DOSSIERS_QUERY_KEY = ["audit", "rapports"] as const;
const dossierQueryKey = (rapportId: string) => ["audit", "rapports", rapportId] as const;
const HISTORIQUE_QUERY_KEY = ["audit", "historique"] as const;

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
    },
  });
}
