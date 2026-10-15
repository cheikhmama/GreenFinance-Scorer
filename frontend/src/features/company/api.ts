import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
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
  updateMyCompanyProfile,
} from "@/shared/api/generated/company/company";
import type {
  BodyRegisterCompany,
  BodyReplyToRegistrationInfoRequest,
  BodySubmitCompanyReportCorrection,
  EntreprisePublic,
  GroupeCompletude,
  ModifierProfilEntrepriseRequest,
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
import { useUnreadNotificationsCount } from "@/shared/notifications/api";

/** Clés de requête de l'espace Entreprise (FRONTEND-ARCHITECTURE.md §3.2) : une fabrique typée,
 * mêmes valeurs qu'avant — un rapport est rangé sous la liste, invalider la liste l'invalide. */
export const companyKeys = {
  all: ["company"] as const,
  reports: () => [...companyKeys.all, "rapports"] as const,
  report: (rapportId: string) => [...companyKeys.reports(), rapportId] as const,
  checklist: (rapportId: string, analyseeLe: string | null) =>
    [...companyKeys.report(rapportId), "checklist", analyseeLe] as const,
  profile: () => [...companyKeys.all, "profil"] as const,
  lei: (lei: string | null | undefined) => [...companyKeys.all, "lei-verification", lei] as const,
  registrationStatus: (token: string | null) =>
    [...companyKeys.all, "registration-status", token] as const,
};

/** Les données d'un rapport changent à chaque étape d'examen : fraîches 30 s au plus. */
const FRAICHEUR_RAPPORTS_MS = 30_000;

/** GET /company/rapports — la liste des rapports de l'entreprise connectée. Suivie tant qu'une
 * analyse tourne : tableau de bord et liste passent seuls à l'état suivant (spec §6). */
export function useCompanyReports() {
  return useQuery<RapportESGPublic[], ApiError>({
    queryKey: companyKeys.reports(),
    queryFn: () => listCompanyReports(),
    staleTime: FRAICHEUR_RAPPORTS_MS,
    refetchInterval: (query) =>
      query.state.data?.some((r) => r.status === "EXTRACTING") ? DELAI_SUIVI_ANALYSE_MS : false,
  });
}

/** Intervalle de rafraîchissement pendant l'analyse du fichier d'un brouillon (tâche 5.8). */
export const DELAI_SUIVI_ANALYSE_MS = 5000;

/** GET /company/rapports/{id} — une seule requête pour tous les niveaux d'une déclaration
 * (synthèse, pilier, indicateur : `select`). Suivie tant qu'une extraction est en cours. */
export function rapportQueryOptions(rapportId: string) {
  return queryOptions<RapportESGDetail, ApiError>({
    queryKey: companyKeys.report(rapportId),
    queryFn: () => getCompanyReport(rapportId),
    enabled: rapportId.length > 0,
    staleTime: FRAICHEUR_RAPPORTS_MS,
    refetchInterval: (query) =>
      query.state.data?.status === "EXTRACTING" ? DELAI_SUIVI_ANALYSE_MS : false,
  });
}

/** L'examen est fait par des personnes : pas de suivi périodique. Une décision produit une
 * notification ; quand le compteur de non-lues (déjà suivi chaque minute) augmente, les
 * déclarations sont relues (spec §6). Une baisse (lecture) ne déclenche rien. */
export function useActualisationSurNotification() {
  const queryClient = useQueryClient();
  const { data: nonLues } = useUnreadNotificationsCount();
  const precedent = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (nonLues === undefined) return;
    if (precedent.current !== undefined && nonLues > precedent.current) {
      queryClient.invalidateQueries({ queryKey: companyKeys.reports() });
    }
    precedent.current = nonLues;
  }, [nonLues, queryClient]);
}

/** GET /reports/{id}/checklist — trouvés / attendus par groupe, jamais de valeurs (tâche 5.8). */
export function useReportChecklist(rapportId: string, analyseTermineeLe: string | null) {
  return useQuery<GroupeCompletude[], ApiError>({
    queryKey: companyKeys.checklist(rapportId, analyseTermineeLe),
    queryFn: () => getReportChecklist(rapportId),
    enabled: analyseTermineeLe !== null,
  });
}

function useRafraichirRapport(rapportId: string) {
  const queryClient = useQueryClient();
  return (rapport: ReportResponse) => {
    queryClient.invalidateQueries({ queryKey: companyKeys.reports() });
    queryClient.invalidateQueries({ queryKey: companyKeys.report(rapportId) });
    return rapport;
  };
}

/** POST /reports — ouvre une déclaration (brouillon) pour un exercice (tâche 5.8). */
export function useOpenDeclaration() {
  const queryClient = useQueryClient();
  return useMutation<ReportResponse, ApiError, ReportCreateRequest>({
    mutationFn: (payload) => openReport(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: companyKeys.reports() });
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
      queryClient.invalidateQueries({ queryKey: companyKeys.reports() });
      queryClient.removeQueries({ queryKey: companyKeys.report(rapportId) });
    },
  });
}

/** GET /company/profil — la fiche entreprise telle que vue par les investisseurs. Nom, secteur
 * et pays restent réservés à l'Admin ; description, site officiel et montant minimum sont
 * modifiables par l'Entreprise elle-même (voir useUpdateMyCompanyProfile ci-dessous). */
export function useMyCompanyProfile() {
  return useQuery<EntreprisePublic, ApiError>({
    queryKey: companyKeys.profile(),
    queryFn: () => getMyCompanyProfile(),
    staleTime: 5 * 60 * 1000,
  });
}

/** PATCH /company/profil — description, site officiel et montant minimum de sa propre
 * entreprise. */
export function useUpdateMyCompanyProfile() {
  const queryClient = useQueryClient();
  return useMutation<EntreprisePublic, ApiError, ModifierProfilEntrepriseRequest>({
    mutationFn: (payload) => updateMyCompanyProfile(payload),
    onSuccess: (entreprise) => {
      queryClient.setQueryData(companyKeys.profile(), entreprise);
    },
  });
}

/** GET /company/lei-verification — contrôle GLEIF en direct (tâche 5.9), seulement si un LEI est
 * déclaré ; gardé dix minutes pour ne pas solliciter la GLEIF à chaque page. */
export function useMyLeiVerification(lei: string | null | undefined) {
  return useQuery<VerificationLei, ApiError>({
    queryKey: companyKeys.lei(lei),
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
      queryClient.invalidateQueries({ queryKey: companyKeys.reports() });
      queryClient.invalidateQueries({ queryKey: companyKeys.report(rapportId) });
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
    queryKey: companyKeys.registrationStatus(token),
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
      queryClient.setQueryData(companyKeys.registrationStatus(token), vue);
    },
  });
}
