import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ApiError } from "@/shared/api/errors";
import {
  acceptInstitutionInvitation,
  compareCompaniesForResearcher,
  correctAnalysis,
  createAnalysis,
  declineInstitutionInvitation,
  getAnalysisDetail,
  getAnalysisHistory,
  getPublishedCompanyDetailForResearcher,
  listMyAnalyses,
  listMyAssignedProjects,
  listMyInstitutionInvitations,
  listProjectDocumentsForResearcher,
  listProjectScopeForResearcher,
  listPublishedCompaniesForResearcher,
  submitAnalysis,
  updateAnalysis,
} from "@/shared/api/generated/researcher/researcher";
import type {
  AnalyseDetail,
  AnalysePublic,
  CreerAnalyseRequest,
  DocumentProjetPublic,
  EntreprisePerimetrePublic,
  EntrepriseDetailInvestisseur,
  EntreprisePublieePublic,
  ModifierAnalyseRequest,
  PageEntreprisePublieePublic,
  ProjetAffecte,
  RattachementPublic,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

export const TAILLE_PAGE_RESEARCHER = 10;
/** Plafond serveur pour /researcher/comparaison (app/investor/entreprises.py::
 * _MAX_ENTREPRISES_COMPARAISON) — dupliqué ici pour guider la sélection côté UI avant l'appel,
 * jamais pour remplacer la vérification serveur. */
export const MAX_ENTREPRISES_COMPARAISON = 4;

const ENTREPRISES_KEY = ["researcher", "entreprises"] as const;
const entrepriseKey = (id: string) => ["researcher", "entreprises", id] as const;
const RATTACHEMENTS_KEY = ["researcher", "rattachements"] as const;
const PROJETS_KEY = ["researcher", "projets"] as const;
const perimetreKey = (projetId: string) => ["researcher", "projets", projetId, "perimetre"] as const;
const documentsKey = (projetId: string) => ["researcher", "projets", projetId, "documents"] as const;
const ANALYSES_KEY = ["researcher", "analyses"] as const;
const analyseKey = (id: string) => ["researcher", "analyses", id] as const;
const historiqueKey = (id: string) => ["researcher", "analyses", id, "historique"] as const;

function pageSuivante<T extends { page: number; pages: number }>(dernierePage: T): number | undefined {
  return dernierePage.page < dernierePage.pages ? dernierePage.page + 1 : undefined;
}

export function usePublishedCompaniesForResearcher(filtres: { recherche?: string }) {
  return useInfiniteQuery<PageEntreprisePublieePublic, ApiError>({
    queryKey: [...ENTREPRISES_KEY, filtres],
    queryFn: ({ pageParam }) =>
      listPublishedCompaniesForResearcher({
        recherche: filtres.recherche || undefined,
        page: pageParam as number,
        page_size: TAILLE_PAGE_RESEARCHER,
      }),
    initialPageParam: 1,
    getNextPageParam: pageSuivante,
  });
}

export function useCompanyDetailForResearcher(entrepriseId: string) {
  return useQuery<EntrepriseDetailInvestisseur, ApiError>({
    queryKey: entrepriseKey(entrepriseId),
    queryFn: () => getPublishedCompanyDetailForResearcher(entrepriseId),
    enabled: entrepriseId.length > 0,
  });
}

export function useCompareCompaniesForResearcher(entrepriseIds: string[]) {
  return useQuery<EntreprisePublieePublic[], ApiError>({
    queryKey: ["researcher", "comparaison", entrepriseIds],
    queryFn: () => compareCompaniesForResearcher({ entreprise_ids: entrepriseIds }),
    enabled: entrepriseIds.length >= 2,
  });
}

export function useMyInvitations() {
  return useQuery<RattachementPublic[], ApiError>({
    queryKey: RATTACHEMENTS_KEY,
    queryFn: () => listMyInstitutionInvitations(),
  });
}

function useRespondInvitation(accept: boolean) {
  const queryClient = useQueryClient();
  return useMutation<RattachementPublic, ApiError, string>({
    mutationFn: (rattachementId) =>
      accept ? acceptInstitutionInvitation(rattachementId) : declineInstitutionInvitation(rattachementId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: RATTACHEMENTS_KEY });
    },
  });
}

export function useAcceptInvitation() {
  return useRespondInvitation(true);
}

export function useDeclineInvitation() {
  return useRespondInvitation(false);
}

export function useMyAssignedProjects() {
  return useQuery<ProjetAffecte[], ApiError>({
    queryKey: PROJETS_KEY,
    queryFn: () => listMyAssignedProjects(),
  });
}

/** Périmètre du projet (ProjetEntreprise) — les seules entreprises qu'une analyse de ce projet
 * peut comparer (voir app/researcher/analyses.py::_verifier_perimetre_et_recuperer_snapshots).
 * Jamais la liste complète des entreprises publiées de la plateforme. */
export function useProjectScope(projetId: string) {
  return useQuery<EntreprisePerimetrePublic[], ApiError>({
    queryKey: perimetreKey(projetId),
    queryFn: () => listProjectScopeForResearcher(projetId),
    enabled: projetId.length > 0,
  });
}

/** Documents explicitement mis à disposition du projet par l'Institution (ProjetDocument) —
 * distinct du périmètre : une entreprise peut être autorisée sans qu'aucun document ne lui soit
 * encore associé. */
export function useProjectDocuments(projetId: string) {
  return useQuery<DocumentProjetPublic[], ApiError>({
    queryKey: documentsKey(projetId),
    queryFn: () => listProjectDocumentsForResearcher(projetId),
    enabled: projetId.length > 0,
  });
}

export function useMyAnalyses() {
  return useQuery<AnalysePublic[], ApiError>({
    queryKey: ANALYSES_KEY,
    queryFn: () => listMyAnalyses(),
  });
}

export function useAnalysisDetail(analyseId: string) {
  return useQuery<AnalyseDetail, ApiError>({
    queryKey: analyseKey(analyseId),
    queryFn: () => getAnalysisDetail(analyseId),
    enabled: analyseId.length > 0,
  });
}

export function useCreateAnalysis(projetId: string) {
  const queryClient = useQueryClient();
  return useMutation<AnalyseDetail, ApiError, CreerAnalyseRequest>({
    mutationFn: (payload) => createAnalysis(projetId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ANALYSES_KEY });
    },
  });
}

export function useUpdateAnalysis(analyseId: string) {
  const queryClient = useQueryClient();
  return useMutation<AnalyseDetail, ApiError, ModifierAnalyseRequest>({
    mutationFn: (payload) => updateAnalysis(analyseId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ANALYSES_KEY });
      queryClient.invalidateQueries({ queryKey: analyseKey(analyseId) });
    },
  });
}

export function useSubmitAnalysis(analyseId: string) {
  const queryClient = useQueryClient();
  return useMutation<AnalyseDetail, ApiError, void>({
    mutationFn: () => submitAnalysis(analyseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ANALYSES_KEY });
      queryClient.invalidateQueries({ queryKey: analyseKey(analyseId) });
    },
  });
}

/** Crée une NOUVELLE analyse (version+1) — jamais une réécriture, voir
 * app/researcher/analyses.py::corriger_analyse. */
export function useCorrectAnalysis(analyseId: string) {
  const queryClient = useQueryClient();
  return useMutation<AnalyseDetail, ApiError, ModifierAnalyseRequest>({
    mutationFn: (payload) => correctAnalysis(analyseId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ANALYSES_KEY });
      queryClient.invalidateQueries({ queryKey: analyseKey(analyseId) });
    },
  });
}

/** Chaîne complète des versions (v1 -> correction -> v2 -> ...), reconstruite côté serveur à
 * partir de n'importe quelle version — voir app/researcher/analyses.py::lister_versions. */
export function useAnalysisHistory(analyseId: string) {
  return useQuery<AnalysePublic[], ApiError>({
    queryKey: historiqueKey(analyseId),
    queryFn: () => getAnalysisHistory(analyseId),
    enabled: analyseId.length > 0,
  });
}
