import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ApiError } from "@/shared/api/errors";
import {
  getCompanyReport,
  getMyCompanyProfile,
  getMyLeiVerification,
  getRegistrationStatus,
  listCompanyReports,
  registerCompany,
  replyToRegistrationInfoRequest,
  submitCompanyReportCorrection,
} from "@/shared/api/generated/company/company";
import type {
  BodyRegisterCompany,
  BodyReplyToRegistrationInfoRequest,
  BodySubmitCompanyReportCorrection,
  EntreprisePublic,
  GroupeCompletude,
  RapportESGDetail,
  RapportESGPublic,
  RegistrationStatusView,
  ReportCreateRequest,
  ReportResponse,
  VerificationLei,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  attachReportFile,
  discardReport,
  getReportChecklist,
  openReport,
  submitReport,
} from "@/shared/api/generated/reports/reports";

const REPORTS_QUERY_KEY = ["company", "rapports"] as const;
const reportQueryKey = (rapportId: string) => ["company", "rapports", rapportId] as const;

/** GET /company/rapports — la liste des rapports de l'entreprise connectée. */
export function useCompanyReports() {
  return useQuery<RapportESGPublic[], ApiError>({
    queryKey: REPORTS_QUERY_KEY,
    queryFn: () => listCompanyReports(),
  });
}

/** Intervalle de rafraîchissement pendant l'analyse du fichier d'un brouillon (tâche 5.8). */
export const DELAI_SUIVI_ANALYSE_MS = 5000;

/** GET /company/rapports/{id} — détail, indicateurs et données carbone inclus (aucune valeur
 * pour un brouillon, tâche 5.8). Suivi automatique tant qu'une extraction est en cours. */
export function useCompanyReport(rapportId: string) {
  return useQuery<RapportESGDetail, ApiError>({
    queryKey: reportQueryKey(rapportId),
    queryFn: () => getCompanyReport(rapportId),
    enabled: rapportId.length > 0,
    refetchInterval: (query) =>
      query.state.data?.status === "EXTRACTING" ? DELAI_SUIVI_ANALYSE_MS : false,
  });
}

/** GET /reports/{id}/checklist — trouvés / attendus par groupe, jamais de valeurs (tâche 5.8). */
export function useReportChecklist(rapportId: string, analyseTermineeLe: string | null) {
  return useQuery<GroupeCompletude[], ApiError>({
    queryKey: [...reportQueryKey(rapportId), "checklist", analyseTermineeLe],
    queryFn: () => getReportChecklist(rapportId),
    enabled: analyseTermineeLe !== null,
  });
}

function useRafraichirRapport(rapportId: string) {
  const queryClient = useQueryClient();
  return (rapport: ReportResponse) => {
    queryClient.invalidateQueries({ queryKey: REPORTS_QUERY_KEY });
    queryClient.invalidateQueries({ queryKey: reportQueryKey(rapportId) });
    return rapport;
  };
}

/** POST /reports — ouvre une déclaration (brouillon) pour un exercice (tâche 5.8). */
export function useOpenDeclaration() {
  const queryClient = useQueryClient();
  return useMutation<ReportResponse, ApiError, ReportCreateRequest>({
    mutationFn: (payload) => openReport(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: REPORTS_QUERY_KEY });
    },
  });
}

/** POST /reports/{id}/file — joint (ou remplace) le PDF d'un brouillon et lance son analyse. */
export function useAttachDraftFile(rapportId: string) {
  const rafraichir = useRafraichirRapport(rapportId);
  return useMutation<ReportResponse, ApiError, File>({
    mutationFn: (file) => attachReportFile(rapportId, { file }),
    onSuccess: rafraichir,
  });
}

/** POST /reports/{id}/submit — soumission : le rapport est verrouillé ; la réponse est le reçu. */
export function useSubmitDraft(rapportId: string) {
  const rafraichir = useRafraichirRapport(rapportId);
  return useMutation<ReportResponse, ApiError, void>({
    mutationFn: () => submitReport(rapportId),
    onSuccess: rafraichir,
  });
}

/** DELETE /reports/{id} — abandon d'un brouillon. */
export function useDiscardDraft(rapportId: string) {
  const queryClient = useQueryClient();
  return useMutation<void, ApiError, void>({
    mutationFn: () => discardReport(rapportId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: REPORTS_QUERY_KEY });
      queryClient.removeQueries({ queryKey: reportQueryKey(rapportId) });
    },
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

/** GET /company/lei-verification — contrôle GLEIF en direct (tâche 5.9), seulement si un LEI est
 * déclaré ; gardé dix minutes pour ne pas solliciter la GLEIF à chaque page. */
export function useMyLeiVerification(lei: string | null | undefined) {
  return useQuery<VerificationLei, ApiError>({
    queryKey: ["company", "lei-verification", lei],
    queryFn: () => getMyLeiVerification(),
    enabled: Boolean(lei),
    staleTime: 10 * 60 * 1000,
    retry: false,
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

/** POST /companies/register — public, multipart (lettre de mandat, tâche 5.2). Réponse 202
 * identique que la demande aboutisse ou non (app/company/registration.py) : le demandeur est
 * informé par e-mail, avec son lien de suivi. */
export function useRegisterCompany() {
  return useMutation<unknown, ApiError, BodyRegisterCompany>({
    mutationFn: (payload) => registerCompany(payload),
    retry: false,
  });
}

/** POST /companies/registration-status — public : le jeton reçu par e-mail, dans le corps. */
export function useRegistrationStatus(token: string | null) {
  return useQuery<RegistrationStatusView, ApiError>({
    queryKey: ["company", "registration-status", token],
    queryFn: () => getRegistrationStatus({ token: token ?? "" }),
    enabled: token !== null,
    retry: false,
  });
}

/** POST /companies/registration-status/reply — nouvelle lettre de mandat en réponse à une
 * demande d'informations. */
export function useReplyToRegistrationInfoRequest(token: string) {
  const queryClient = useQueryClient();
  return useMutation<
    RegistrationStatusView,
    ApiError,
    Omit<BodyReplyToRegistrationInfoRequest, "token">
  >({
    mutationFn: (payload) => replyToRegistrationInfoRequest({ ...payload, token }),
    retry: false,
    onSuccess: (vue) => {
      queryClient.setQueryData(["company", "registration-status", token], vue);
    },
  });
}
