import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ApiError } from "@/shared/api/errors";
import { downloadFile } from "@/shared/api/download";
import {
  approveAnalysis,
  assignResearcherToProject,
  closeProject,
  createProject,
  getAnalysisDetailForInstitution,
  getProjectDetail,
  inviteResearcher,
  listAvailableResearchers,
  listMyProjects,
  listMyResearchers,
  requestAnalysisCorrection,
} from "@/shared/api/generated/institution/institution";
import type {
  AffectationPublic,
  AffecterChercheurRequest,
  AnalyseDetail,
  AnalysePublic,
  ChercheurDisponible,
  CreerProjetRequest,
  DecisionAnalyseRequest,
  InviterChercheurRequest,
  ProjetDetail,
  ProjetPublic,
  RattachementPublic,
  StatutRattachement,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

const CHERCHEURS_DISPONIBLES_KEY = ["institution", "chercheurs", "disponibles"] as const;
const MES_CHERCHEURS_KEY = ["institution", "chercheurs"] as const;
const PROJETS_KEY = ["institution", "projets"] as const;
const projetKey = (id: string) => ["institution", "projets", id] as const;
const analyseKey = (id: string) => ["institution", "analyses", id] as const;

export function useAvailableResearchers() {
  return useQuery<ChercheurDisponible[], ApiError>({
    queryKey: CHERCHEURS_DISPONIBLES_KEY,
    queryFn: () => listAvailableResearchers(),
  });
}

export function useMyResearchers(statut?: StatutRattachement) {
  return useQuery<RattachementPublic[], ApiError>({
    queryKey: [...MES_CHERCHEURS_KEY, statut],
    queryFn: () => listMyResearchers({ statut }),
  });
}

export function useInviteResearcher() {
  const queryClient = useQueryClient();
  return useMutation<RattachementPublic, ApiError, InviterChercheurRequest>({
    mutationFn: (payload) => inviteResearcher(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CHERCHEURS_DISPONIBLES_KEY });
      queryClient.invalidateQueries({ queryKey: MES_CHERCHEURS_KEY });
    },
  });
}

export function useMyProjects() {
  return useQuery<ProjetPublic[], ApiError>({
    queryKey: PROJETS_KEY,
    queryFn: () => listMyProjects(),
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation<ProjetPublic, ApiError, CreerProjetRequest>({
    mutationFn: (payload) => createProject(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROJETS_KEY });
    },
  });
}

export function useProjectDetail(projetId: string) {
  return useQuery<ProjetDetail, ApiError>({
    queryKey: projetKey(projetId),
    queryFn: () => getProjectDetail(projetId),
    enabled: projetId.length > 0,
  });
}

export function useAssignResearcher(projetId: string) {
  const queryClient = useQueryClient();
  return useMutation<AffectationPublic, ApiError, AffecterChercheurRequest>({
    mutationFn: (payload) => assignResearcherToProject(projetId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projetKey(projetId) });
    },
  });
}

export function useCloseProject(projetId: string) {
  const queryClient = useQueryClient();
  return useMutation<ProjetPublic, ApiError, void>({
    mutationFn: () => closeProject(projetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROJETS_KEY });
      queryClient.invalidateQueries({ queryKey: projetKey(projetId) });
    },
  });
}

export function useAnalysisDetailForInstitution(analyseId: string) {
  return useQuery<AnalyseDetail, ApiError>({
    queryKey: analyseKey(analyseId),
    queryFn: () => getAnalysisDetailForInstitution(analyseId),
    enabled: analyseId.length > 0,
  });
}

export function useApproveAnalysis(analyseId: string, projetId: string) {
  const queryClient = useQueryClient();
  return useMutation<AnalysePublic, ApiError, DecisionAnalyseRequest>({
    mutationFn: (payload) => approveAnalysis(analyseId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: analyseKey(analyseId) });
      queryClient.invalidateQueries({ queryKey: projetKey(projetId) });
    },
  });
}

export function useRequestAnalysisCorrection(analyseId: string, projetId: string) {
  const queryClient = useQueryClient();
  return useMutation<AnalysePublic, ApiError, DecisionAnalyseRequest>({
    mutationFn: (payload) => requestAnalysisCorrection(analyseId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: analyseKey(analyseId) });
      queryClient.invalidateQueries({ queryKey: projetKey(projetId) });
    },
  });
}

/** GET /institution/analyses/{id}/export — décrémente InstitutionProfil.quota_export côté
 * serveur ; jamais un hook TanStack Query (une action, pas une donnée mise en cache). */
export function exportAnalysisFile(analyseId: string, titreAnalyse: string): Promise<void> {
  return downloadFile(`/institution/analyses/${analyseId}/export`, `analyse-${titreAnalyse}.csv`);
}
