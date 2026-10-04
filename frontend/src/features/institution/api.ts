import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { downloadFile } from "@/shared/api/download";
import type { ApiError } from "@/shared/api/errors";
import { chargerToutesLesPages, TAILLE_PAGE_TABLE } from "@/shared/api/toutesLesPages";
import type {
  AffectationPublic,
  AffecterChercheurRequest,
  AffiliationStatus,
  AjouterDocumentRequest,
  AjouterEntreprisePerimetreRequest,
  AnalyseDetail,
  AnalyseInstitutionPublic,
  AnalysePublic,
  AnalysisStatus,
  ChercheurDisponible,
  CreerProjetRequest,
  DecisionAnalyseRequest,
  DocumentProjetPublic,
  EntrepriseDetailInvestisseur,
  EntreprisePerimetrePublic,
  InstitutionProfilPublic,
  InviterChercheurRequest,
  EntreprisePublieePublic,
  PageEntreprisePublieePublic,
  ProjetDetail,
  ProjetPublic,
  RattachementPublic,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  addCompanyToProjectScope,
  addDocumentToProject,
  approveAnalysis,
  assignResearcherToProject,
  closeProject,
  createProject,
  getAnalysisDetailForInstitution,
  getAnalysisHistoryForInstitution,
  getMyInstitutionProfile,
  getProjectDetail,
  getPublishedCompanyDetailForInstitution,
  inviteResearcher,
  listAvailableResearchers,
  listMyAnalysesForInstitution,
  listMyProjects,
  listMyResearchers,
  listProjectDocuments,
  listProjectScope,
  listPublishedCompaniesForInstitution,
  requestAnalysisCorrection,
} from "@/shared/api/generated/institution/institution";

export const TAILLE_PAGE_INSTITUTION = 10;

const CHERCHEURS_DISPONIBLES_KEY = ["institution", "chercheurs", "disponibles"] as const;
const MES_CHERCHEURS_KEY = ["institution", "chercheurs"] as const;
const PROJETS_KEY = ["institution", "projets"] as const;
const projetKey = (id: string) => ["institution", "projets", id] as const;
const perimetreKey = (projetId: string) =>
  ["institution", "projets", projetId, "perimetre"] as const;
const documentsKey = (projetId: string) =>
  ["institution", "projets", projetId, "documents"] as const;
const MES_ANALYSES_KEY = ["institution", "analyses"] as const;
const analyseKey = (id: string) => ["institution", "analyses", id] as const;
const historiqueKey = (id: string) => ["institution", "analyses", id, "historique"] as const;
const ENTREPRISES_KEY = ["institution", "entreprises"] as const;
const entrepriseKey = (id: string) => ["institution", "entreprises", id] as const;

function pageSuivante<T extends { page: number; pages: number }>(
  dernierePage: T,
): number | undefined {
  return dernierePage.page < dernierePage.pages ? dernierePage.page + 1 : undefined;
}

/** GET /institution/profil — quota d'export restant, en lecture seule (décrémenté
 * automatiquement à chaque export réel, voir useExport côté analyses). */
export function useMyInstitutionProfile() {
  return useQuery<InstitutionProfilPublic, ApiError>({
    queryKey: ["institution", "profil"],
    queryFn: () => getMyInstitutionProfile(),
  });
}

export function useAvailableResearchers() {
  return useQuery<ChercheurDisponible[], ApiError>({
    queryKey: CHERCHEURS_DISPONIBLES_KEY,
    queryFn: () => listAvailableResearchers(),
  });
}

export function useMyResearchers(statut?: AffiliationStatus) {
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

/** Périmètre du projet (ProjetEntreprise) — les entreprises que le Chercheur affecté pourra
 * comparer dans une analyse (voir app/researcher/analyses.py::
 * _verifier_perimetre_et_recuperer_snapshots). */
export function useProjectScope(projetId: string) {
  return useQuery<EntreprisePerimetrePublic[], ApiError>({
    queryKey: perimetreKey(projetId),
    queryFn: () => listProjectScope(projetId),
    enabled: projetId.length > 0,
  });
}

export function useAddCompanyToScope(projetId: string) {
  const queryClient = useQueryClient();
  return useMutation<EntreprisePerimetrePublic, ApiError, AjouterEntreprisePerimetreRequest>({
    mutationFn: (payload) => addCompanyToProjectScope(projetId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: perimetreKey(projetId) });
      queryClient.invalidateQueries({ queryKey: projetKey(projetId) });
    },
  });
}

/** Documents explicitement mis à disposition (ProjetDocument) — distinct du périmètre : une
 * entreprise autorisée n'y donne pas automatiquement accès à son rapport tant qu'il n'est pas
 * ici (voir app/institution/projets.py::ajouter_document). */
export function useProjectDocuments(projetId: string) {
  return useQuery<DocumentProjetPublic[], ApiError>({
    queryKey: documentsKey(projetId),
    queryFn: () => listProjectDocuments(projetId),
    enabled: projetId.length > 0,
  });
}

export function useAddDocument(projetId: string) {
  const queryClient = useQueryClient();
  return useMutation<DocumentProjetPublic, ApiError, AjouterDocumentRequest>({
    mutationFn: (payload) => addDocumentToProject(projetId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentsKey(projetId) });
      queryClient.invalidateQueries({ queryKey: projetKey(projetId) });
    },
  });
}

/** Catalogue des entreprises publiées — sert à composer le périmètre d'un projet (recherche par
 * nom/secteur), jamais une saisie libre d'identité (même principe que partout ailleurs). */
export function usePublishedCompaniesForInstitution(filtres: { recherche?: string }) {
  return useInfiniteQuery<PageEntreprisePublieePublic, ApiError>({
    queryKey: [...ENTREPRISES_KEY, filtres],
    queryFn: ({ pageParam }) =>
      listPublishedCompaniesForInstitution({
        recherche: filtres.recherche || undefined,
        page: pageParam as number,
        page_size: TAILLE_PAGE_INSTITUTION,
      }),
    initialPageParam: 1,
    getNextPageParam: pageSuivante,
  });
}

/** Catalogue complet pour la table de données (tâche 5.18) : recherche, filtres et tri se font
 * côté navigateur. */
export function useTableEntreprisesInstitution() {
  return useQuery<EntreprisePublieePublic[], ApiError>({
    queryKey: [...ENTREPRISES_KEY, "table"],
    queryFn: () =>
      chargerToutesLesPages((page) =>
        listPublishedCompaniesForInstitution({ page, page_size: TAILLE_PAGE_TABLE }),
      ),
  });
}

export function useCompanyDetailForInstitution(entrepriseId: string) {
  return useQuery<EntrepriseDetailInvestisseur, ApiError>({
    queryKey: entrepriseKey(entrepriseId),
    queryFn: () => getPublishedCompanyDetailForInstitution(entrepriseId),
    enabled: entrepriseId.length > 0,
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

/** Toutes les analyses reçues, tous projets confondus — seule vue d'ensemble permettant de
 * repérer ce qui reste à décider sans ouvrir chaque projet un par un (voir ProjectDetailPage,
 * qui ne montre que les analyses d'un seul projet à la fois). */
export function useMyAnalysesForInstitution(statut?: AnalysisStatus) {
  return useQuery<AnalyseInstitutionPublic[], ApiError>({
    queryKey: [...MES_ANALYSES_KEY, statut],
    queryFn: () => listMyAnalysesForInstitution({ statut }),
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

/** Chaîne complète des versions (v1 -> correction -> v2 -> ...), reconstruite côté serveur à
 * partir de n'importe quelle version — voir app/researcher/analyses.py::lister_versions. */
export function useAnalysisHistoryForInstitution(analyseId: string) {
  return useQuery<AnalysePublic[], ApiError>({
    queryKey: historiqueKey(analyseId),
    queryFn: () => getAnalysisHistoryForInstitution(analyseId),
    enabled: analyseId.length > 0,
  });
}

/** GET /institution/analyses/{id}/export — décrémente InstitutionProfil.quota_export côté
 * serveur ; jamais un hook TanStack Query (une action, pas une donnée mise en cache). */
export function exportAnalysisFile(analyseId: string, titreAnalyse: string): Promise<void> {
  return downloadFile(`/institution/analyses/${analyseId}/export`, `analyse-${titreAnalyse}.csv`);
}
