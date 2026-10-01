import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ApiError } from "@/shared/api/errors";
import {
  assignReportAuditor,
  createUser,
  deactivateUser,
  deleteCompanyLogo,
  getAdminActorsOverview,
  getAdminDashboard,
  getAdminESGPerformance,
  getAdminReport,
  getCompanyAdmin,
  getReportFinancials,
  listReportExtractionRuns,
  getCompanyKyc,
  listAdminCompanyReports,
  listAllCompanies,
  listAllReports,
  listAnalysesAdmin,
  listAuditLog,
  listAuditorWorkload,
  listCompaniesToRepublish,
  listCompaniesWithScore,
  listFailedExtractionReports,
  listOrphanReportsInValidation,
  listOverdueReports,
  listPortfoliosAdmin,
  listProjectsAdmin,
  listPublishableCompanies,
  listReportOpinions,
  listReportsInValidation,
  listReportsToAssign,
  listReportVersions,
  listUsersAwaitingActivation,
  listUsersByRole,
  onboardCompany,
  publishCompany,
  reactivateCompany,
  reactivateUser,
  recalculateReportScore,
  rejectReport,
  requestReportCorrection,
  retryExtraction,
  suspendCompany,
  updateReportFinancials,
  updateCompanyIdentifiers,
  updateCompanyProfile,
  uploadCompanyLogo,
  validateReport,
  verifyReportScorability,
} from "@/shared/api/generated/admin/admin";
import type {
  AffecterAuditeurRequest,
  AnalysisStatus,
  ApercuActeursAdmin,
  AvisAuditAdmin,
  ReportFinancials,
  ReportFinancialsRequest,
  CompanyIdentifiers,
  CompanyIdentifiersRequest,
  CompanyOnboardingRequest,
  CompanyOnboardingResult,
  CreerUtilisateurRequest,
  DecisionAdminRequest,
  EntrepriseAdmin,
  EntreprisePublic,
  ExtractionRunPublic,
  KycReport,
  ListAuditLogParams,
  ModifierEntrepriseAdminRequest,
  PageAnalyseAdmin,
  PageChargeAuditeurAdmin,
  PageEntrepriseAdmin,
  PageEntrepriseAvecScoreAdmin,
  PageEntreprisePublic,
  PageJournalAuditPublic,
  PagePortefeuilleAdmin,
  PageProjetAdmin,
  PageRapportESGPublic,
  PageUtilisateurPublic,
  PerformanceESGAdmin,
  ProjectStatus,
  RapportESGDetail,
  RapportESGPublic,
  ReportStatus,
  Role,
  ScoreRecalculeAdmin,
  ScoreVerificationAdmin,
  TableauDeBordAdmin,
  UtilisateurCree,
  UtilisateurPublic,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

// Chargement initial de 3 éléments, puis +3 par clic sur "Voir plus", jusqu'à épuisement réel de
// la liste côté serveur (voir UsersSection / PublishableCompaniesSection).
export const TAILLE_PAGE_ADMIN = 3;

const A_AFFECTER_KEY = ["admin", "rapports", "a-affecter"] as const;
const EN_VALIDATION_KEY = ["admin", "rapports", "en-validation"] as const;
const ECHEC_EXTRACTION_KEY = ["admin", "rapports", "echec-extraction"] as const;
const EXTRACTION_BLOQUEE_KEY = ["admin", "rapports", "extraction-bloquee"] as const;
const ORPHELINS_KEY = ["admin", "rapports", "orphelins"] as const;
const rapportKey = (rapportId: string) => ["admin", "rapports", rapportId] as const;
const scoreVerificationKey = (rapportId: string) =>
  ["admin", "rapports", rapportId, "score-verification"] as const;
const avisKey = (rapportId: string) => ["admin", "rapports", rapportId, "avis"] as const;
const EN_RETARD_KEY = ["admin", "rapports", "en-retard"] as const;
const TOUS_RAPPORTS_KEY = ["admin", "rapports", "tous"] as const;
const PUBLIABLES_KEY = ["admin", "entreprises", "publiables"] as const;
const TOUTES_ENTREPRISES_KEY = ["admin", "entreprises", "toutes"] as const;
const A_REPUBLIER_KEY = ["admin", "entreprises", "a-republier"] as const;
const UTILISATEURS_EN_ATTENTE_KEY = ["admin", "utilisateurs", "en-attente"] as const;
const utilisateursKey = (role: Role) => ["admin", "utilisateurs", role] as const;
const versionsKey = (rapportId: string) => ["admin", "rapports", rapportId, "versions"] as const;
const JOURNAL_AUDIT_KEY = ["admin", "journal-audit"] as const;
const APERCU_ACTEURS_KEY = ["admin", "apercu-acteurs"] as const;
const PERFORMANCE_ESG_KEY = ["admin", "performance-esg"] as const;
const ENTREPRISES_SCORES_KEY = ["admin", "entreprises", "scores"] as const;
const AUDITEURS_CHARGE_KEY = ["admin", "auditeurs", "charge"] as const;
const PORTEFEUILLES_ADMIN_KEY = ["admin", "portefeuilles"] as const;
const ANALYSES_ADMIN_KEY = ["admin", "analyses"] as const;
const PROJETS_ADMIN_KEY = ["admin", "projets"] as const;
const companyReportsKey = (entrepriseId: string) =>
  ["admin", "entreprises", entrepriseId, "rapports"] as const;
const companyDetailKey = (entrepriseId: string) => ["admin", "entreprises", entrepriseId] as const;

function pageSuivante<T extends { page: number; pages: number }>(
  dernierePage: T,
): number | undefined {
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

/** Rapports dont l'extraction automatique a échoué (extraction_erreur renseigné) — invisibles de
 * la file d'affectation normale, voir app/admin/review_queue.py::lister_rapports_echec_extraction. */
export function useFailedExtractionReports() {
  return useQuery<RapportESGPublic[], ApiError>({
    queryKey: ECHEC_EXTRACTION_KEY,
    queryFn: () => listFailedExtractionReports(),
  });
}

/** Rapports PENDING_DECISION sans aucun avis d'audit — état incohérent normalement inatteignable via
 * l'API seule, gardé en visibilité de défense (voir lister_rapports_orphelins_en_validation). */
export function useOrphanReportsInValidation() {
  return useQuery<RapportESGPublic[], ApiError>({
    queryKey: ORPHELINS_KEY,
    queryFn: () => listOrphanReportsInValidation(),
  });
}

/** Relance l'extraction d'un rapport en échec ou bloqué (app/admin/review_queue.py::
 * relancer_extraction) — invalide les deux files d'anomalie, le rapport y disparaît le temps de la
 * nouvelle tentative. */
export function useRetryExtraction() {
  const queryClient = useQueryClient();
  return useMutation<RapportESGPublic, ApiError, string>({
    mutationFn: (rapportId) => retryExtraction(rapportId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ECHEC_EXTRACTION_KEY });
      queryClient.invalidateQueries({ queryKey: EXTRACTION_BLOQUEE_KEY });
    },
  });
}

/** Rapports affectés à un auditeur au-delà du délai attendu (settings.sla_audit_jours), sans
 * décision rendue — voir app/admin/review_queue.py::lister_rapports_en_retard. */
export function useOverdueReports() {
  return useQuery<RapportESGPublic[], ApiError>({
    queryKey: EN_RETARD_KEY,
    queryFn: () => listOverdueReports(),
  });
}

/** Vue globale de tous les rapports, tous statuts confondus, avec filtre optionnel sur le statut
 * (voir app/admin/review_queue.py::lister_tous_les_rapports) — sert le suivi transverse depuis le
 * tableau de bord (ex. "rapports validés"), distinct des files scopées à une étape du workflow. */
export function useAllReports(statut?: ReportStatus) {
  return useInfiniteQuery<PageRapportESGPublic, ApiError>({
    queryKey: [...TOUS_RAPPORTS_KEY, statut ?? "tous"],
    queryFn: ({ pageParam }) =>
      listAllReports({ statut, page: pageParam as number, page_size: TAILLE_PAGE_ADMIN }),
    initialPageParam: 1,
    getNextPageParam: pageSuivante,
  });
}

export function useAdminReport(rapportId: string) {
  return useQuery<RapportESGDetail, ApiError>({
    queryKey: rapportKey(rapportId),
    queryFn: () => getAdminReport(rapportId),
    enabled: rapportId.length > 0,
  });
}

/** Aperçu, avant décision, de si ce rapport pourra être scoré (voir
 * app/scoring/engine.py::score_calculable) — affiché sur la fiche de détail avant que l'Admin ne
 * clique Valider, plutôt que de le laisser découvrir l'échec après coup. */
export function useReportScoreVerification(rapportId: string, enabled: boolean) {
  return useQuery<ScoreVerificationAdmin, ApiError>({
    queryKey: scoreVerificationKey(rapportId),
    queryFn: () => verifyReportScorability(rapportId),
    enabled: enabled && rapportId.length > 0,
  });
}

/** Action de récupération pour un rapport VALIDE sans ScoreESG (état incohérent qui bloque sinon
 * indéfiniment la publication de l'entreprise, voir app/admin/review_queue.py::recalculer_score). */
export function useRecalculateReportScore(rapportId: string) {
  const queryClient = useQueryClient();
  return useMutation<ScoreRecalculeAdmin, ApiError, void>({
    mutationFn: () => recalculateReportScore(rapportId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: rapportKey(rapportId) });
      queryClient.invalidateQueries({ queryKey: PUBLIABLES_KEY });
    },
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

/** Entreprises déjà publiées dont un rapport a été validé après la dernière publication — voir
 * app/admin/review_queue.py::lister_entreprises_a_republier. Republication elle-même : même
 * geste que publier_entreprise (POST .../publier), pas d'action distincte. */
export function useCompaniesToRepublish() {
  return useInfiniteQuery<PageEntreprisePublic, ApiError>({
    queryKey: A_REPUBLIER_KEY,
    queryFn: ({ pageParam }) =>
      listCompaniesToRepublish({ page: pageParam as number, page_size: TAILLE_PAGE_ADMIN }),
    initialPageParam: 1,
    getNextPageParam: pageSuivante,
  });
}

export function usePublishCompany() {
  const queryClient = useQueryClient();
  return useMutation<EntreprisePublic, ApiError, string>({
    mutationFn: (entrepriseId) => publishCompany(entrepriseId),
    onSuccess: (_entreprise, entrepriseId) => {
      queryClient.invalidateQueries({ queryKey: PUBLIABLES_KEY });
      queryClient.invalidateQueries({ queryKey: TOUTES_ENTREPRISES_KEY });
      queryClient.invalidateQueries({ queryKey: A_REPUBLIER_KEY });
      queryClient.invalidateQueries({ queryKey: companyDetailKey(entrepriseId) });
    },
  });
}

export function useSuspendCompany() {
  const queryClient = useQueryClient();
  return useMutation<EntreprisePublic, ApiError, string>({
    mutationFn: (entrepriseId) => suspendCompany(entrepriseId),
    onSuccess: (_entreprise, entrepriseId) => {
      queryClient.invalidateQueries({ queryKey: TOUTES_ENTREPRISES_KEY });
      queryClient.invalidateQueries({ queryKey: companyDetailKey(entrepriseId) });
    },
  });
}

/** PATCH /admin/companies/{id}/onboard — valide (lien d'activation envoyé au titulaire) ou refuse
 * (inscription supprimée, motif envoyé) une inscription en attente (app/admin/onboarding.py). */
const kycKey = (entrepriseId: string) => ["admin", "entreprises", entrepriseId, "kyc"] as const;

/** GET /admin/companies/{id}/kyc (tâche 5.3) — contrôles recalculés à chaque ouverture de la
 * fenêtre (la fiche GLEIF peut changer), jamais mis en cache longtemps. */
export function useCompanyKyc(entrepriseId: string, enabled: boolean) {
  return useQuery<KycReport, ApiError>({
    queryKey: kycKey(entrepriseId),
    queryFn: () => getCompanyKyc(entrepriseId),
    enabled,
    staleTime: 0,
    retry: false,
  });
}

export function useOnboardCompany() {
  const queryClient = useQueryClient();
  return useMutation<
    CompanyOnboardingResult,
    ApiError,
    { entrepriseId: string } & CompanyOnboardingRequest
  >({
    mutationFn: ({ entrepriseId, ...decision }) => onboardCompany(entrepriseId, decision),
    onSuccess: (_resultat, { entrepriseId }) => {
      queryClient.invalidateQueries({ queryKey: TOUTES_ENTREPRISES_KEY });
      queryClient.invalidateQueries({ queryKey: companyDetailKey(entrepriseId) });
      queryClient.invalidateQueries({ queryKey: kycKey(entrepriseId) });
    },
  });
}

export function useReactivateCompany() {
  const queryClient = useQueryClient();
  return useMutation<EntreprisePublic, ApiError, string>({
    mutationFn: (entrepriseId) => reactivateCompany(entrepriseId),
    onSuccess: (_entreprise, entrepriseId) => {
      queryClient.invalidateQueries({ queryKey: TOUTES_ENTREPRISES_KEY });
      queryClient.invalidateQueries({ queryKey: companyDetailKey(entrepriseId) });
    },
  });
}

/** GET /admin/entreprises/{id} — profil complet (identité, description, site officiel, logo,
 * montant minimum) + résumé de statut, pour la fiche de détail Admin d'une entreprise. */
export function useCompanyDetail(entrepriseId: string) {
  return useQuery<EntrepriseAdmin, ApiError>({
    queryKey: companyDetailKey(entrepriseId),
    queryFn: () => getCompanyAdmin(entrepriseId),
    enabled: entrepriseId.length > 0,
  });
}

/** PATCH /admin/entreprises/{id} — remplace entièrement le profil (voir
 * app/admin/schemas.py::ModifierEntrepriseAdminRequest, jamais un patch partiel champ par
 * champ). Écrit directement le résultat dans le cache du détail, comme useUpdateMyProfile. */
export function useUpdateCompanyProfile(entrepriseId: string) {
  const queryClient = useQueryClient();
  return useMutation<EntrepriseAdmin, ApiError, ModifierEntrepriseAdminRequest>({
    mutationFn: (payload) => updateCompanyProfile(entrepriseId, payload),
    onSuccess: (entreprise) => {
      queryClient.setQueryData(companyDetailKey(entrepriseId), entreprise);
      queryClient.invalidateQueries({ queryKey: TOUTES_ENTREPRISES_KEY });
    },
  });
}

/** PATCH /admin/companies/{id}/identifiers (tâche 2.2) — patch partiel : seuls les champs
 * envoyés changent, `null` efface. Relit la fiche (qui expose isin/lei/ticker) au succès. */
export function useUpdateCompanyIdentifiers(entrepriseId: string) {
  const queryClient = useQueryClient();
  return useMutation<CompanyIdentifiers, ApiError, CompanyIdentifiersRequest>({
    mutationFn: (payload) => updateCompanyIdentifiers(entrepriseId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: companyDetailKey(entrepriseId) });
      queryClient.invalidateQueries({ queryKey: TOUTES_ENTREPRISES_KEY });
    },
  });
}

/** GET /admin/reports/{id}/extraction-runs (tâche 5.5) — exécutions du pipeline, plus récente
 * d'abord. */
export function useReportExtractionRuns(rapportId: string) {
  return useQuery<ExtractionRunPublic[], ApiError>({
    queryKey: ["admin", "rapports", rapportId, "extraction-runs"],
    queryFn: () => listReportExtractionRuns(rapportId),
    enabled: rapportId.length > 0,
  });
}

const financialsKey = (rapportId: string) => ["admin", "rapports", rapportId, "financials"] as const;

/** GET /admin/reports/{id}/financials (tâches 2.3, 5.4) — chiffre d'affaires et EVIC de l'exercice
 * du rapport, dont le moteur PCAF a besoin. */
export function useReportFinancials(rapportId: string) {
  return useQuery<ReportFinancials, ApiError>({
    queryKey: financialsKey(rapportId),
    queryFn: () => getReportFinancials(rapportId),
    enabled: rapportId.length > 0,
  });
}

/** PUT /admin/reports/{id}/financials — remplacement complet (un champ omis vaut null). */
export function useUpdateReportFinancials(rapportId: string) {
  const queryClient = useQueryClient();
  return useMutation<ReportFinancials, ApiError, ReportFinancialsRequest>({
    mutationFn: (payload) => updateReportFinancials(rapportId, payload),
    onSuccess: (financieres) => {
      queryClient.setQueryData(financialsKey(rapportId), financieres);
    },
  });
}

/** POST /admin/entreprises/{id}/logo (multipart) — remplace le logo existant s'il y en avait déjà
 * un, même principe que useUploadAvatar côté compte utilisateur. */
export function useUploadCompanyLogo(entrepriseId: string) {
  const queryClient = useQueryClient();
  return useMutation<EntrepriseAdmin, ApiError, File>({
    mutationFn: (fichier) => uploadCompanyLogo(entrepriseId, { fichier }),
    onSuccess: (entreprise) => {
      queryClient.setQueryData(companyDetailKey(entrepriseId), entreprise);
      queryClient.invalidateQueries({ queryKey: TOUTES_ENTREPRISES_KEY });
    },
  });
}

/** DELETE /admin/entreprises/{id}/logo — retour à l'avatar par défaut (initiales). */
export function useDeleteCompanyLogo(entrepriseId: string) {
  const queryClient = useQueryClient();
  return useMutation<EntrepriseAdmin, ApiError, void>({
    mutationFn: () => deleteCompanyLogo(entrepriseId),
    onSuccess: (entreprise) => {
      queryClient.setQueryData(companyDetailKey(entrepriseId), entreprise);
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
        en_attente_activation: enAttente || undefined,
        page: pageParam as number,
        page_size: TAILLE_PAGE_ADMIN,
      }),
    initialPageParam: 1,
    getNextPageParam: pageSuivante,
  });
}

/** Comptes actifs, tous rôles confondus, qui n'ont pas encore cliqué leur lien d'activation —
 * voir app/admin/utilisateurs.py::lister_utilisateurs_en_attente. Distinct de useUsersByRole
 * (scopé à un rôle unique) : sert le raccourci transverse du tableau de bord. */
export function useUsersAwaitingActivation() {
  return useQuery<UtilisateurPublic[], ApiError>({
    queryKey: UTILISATEURS_EN_ATTENTE_KEY,
    queryFn: () => listUsersAwaitingActivation(),
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
      queryClient.invalidateQueries({ queryKey: UTILISATEURS_EN_ATTENTE_KEY });
    },
  });
}

export function useReactivateUser(role: Role) {
  const queryClient = useQueryClient();
  return useMutation<UtilisateurPublic, ApiError, string>({
    mutationFn: (utilisateurId) => reactivateUser(utilisateurId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: utilisateursKey(role) });
      queryClient.invalidateQueries({ queryKey: UTILISATEURS_EN_ATTENTE_KEY });
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

/** Statistiques agrégées des espaces Auditeur/Investisseur/Chercheur/Institution — voir
 * app/admin/apercu.py::construire_apercu_acteurs. Distinct de useAdminDashboard (TableauDeBordAdmin,
 * la vue compacte déjà en place) : sert les onglets acteurs de l'Aperçu Administrateur. */
export function useApercuActeurs() {
  return useQuery<ApercuActeursAdmin, ApiError>({
    queryKey: APERCU_ACTEURS_KEY,
    queryFn: () => getAdminActorsOverview(),
  });
}

/** Score ESG global/E/S/G moyen et couverture, sur le périmètre des entreprises publiées — voir
 * app/admin/apercu.py::calculer_performance_esg. score_*_moyen est `null` quand aucune entreprise
 * du périmètre n'a de valeur exploitable, jamais 0 : ne jamais substituer une valeur par défaut
 * en consommant ce hook. */
export function usePerformanceESG() {
  return useQuery<PerformanceESGAdmin, ApiError>({
    queryKey: PERFORMANCE_ESG_KEY,
    queryFn: () => getAdminESGPerformance(),
  });
}

/** Détail derrière les cartes de performance ESG (indicateur → liste filtrée) — chaque entreprise
 * publiée avec son score admissible, filtrable par secteur/pays. */
export function useCompaniesWithScore(secteur?: string, pays?: string) {
  return useInfiniteQuery<PageEntrepriseAvecScoreAdmin, ApiError>({
    queryKey: [...ENTREPRISES_SCORES_KEY, secteur ?? "", pays ?? ""],
    queryFn: ({ pageParam }) =>
      listCompaniesWithScore({
        secteur: secteur || undefined,
        pays: pays || undefined,
        page: pageParam as number,
        page_size: TAILLE_PAGE_ADMIN,
      }),
    initialPageParam: 1,
    getNextPageParam: pageSuivante,
  });
}

/** Charge de travail par Auditeur actif — détail derrière "Dossiers affectés" de l'onglet
 * Auditeur (app/audit/assignment.py::lister_charge_auditeurs). */
export function useAuditorWorkload(recherche = "") {
  return useInfiniteQuery<PageChargeAuditeurAdmin, ApiError>({
    queryKey: [...AUDITEURS_CHARGE_KEY, recherche],
    queryFn: ({ pageParam }) =>
      listAuditorWorkload({
        recherche: recherche || undefined,
        page: pageParam as number,
        page_size: TAILLE_PAGE_ADMIN,
      }),
    initialPageParam: 1,
    getNextPageParam: pageSuivante,
  });
}

/** Tous les portefeuilles non archivés, tous Investisseurs confondus — détail derrière
 * "Portefeuilles non archivés" de l'onglet Investisseur (app/investor/portfolio.py::
 * lister_portefeuilles_admin). */
export function usePortfoliosAdmin(recherche = "") {
  return useInfiniteQuery<PagePortefeuilleAdmin, ApiError>({
    queryKey: [...PORTEFEUILLES_ADMIN_KEY, recherche],
    queryFn: ({ pageParam }) =>
      listPortfoliosAdmin({
        recherche: recherche || undefined,
        page: pageParam as number,
        page_size: TAILLE_PAGE_ADMIN,
      }),
    initialPageParam: 1,
    getNextPageParam: pageSuivante,
  });
}

/** Toutes les analyses Chercheur, filtrable par statut — détail derrière "Analyses par statut" de
 * l'onglet Chercheur/Institution (app/researcher/analyses.py::lister_analyses_admin). Une ligne =
 * une version précise, jamais fusionnée avec ses versions précédentes/suivantes. */
export function useAnalysesAdmin(statut?: AnalysisStatus) {
  return useInfiniteQuery<PageAnalyseAdmin, ApiError>({
    queryKey: [...ANALYSES_ADMIN_KEY, statut ?? "tous"],
    queryFn: ({ pageParam }) =>
      listAnalysesAdmin({ statut, page: pageParam as number, page_size: TAILLE_PAGE_ADMIN }),
    initialPageParam: 1,
    getNextPageParam: pageSuivante,
  });
}

/** Tous les projets Institution, filtrable par statut — détail derrière "Projets ouverts/clôturés"
 * de l'onglet Institution (app/institution/projets.py::lister_projets_admin). */
export function useProjectsAdmin(statut?: ProjectStatus) {
  return useInfiniteQuery<PageProjetAdmin, ApiError>({
    queryKey: [...PROJETS_ADMIN_KEY, statut ?? "tous"],
    queryFn: ({ pageParam }) =>
      listProjectsAdmin({ statut, page: pageParam as number, page_size: TAILLE_PAGE_ADMIN }),
    initialPageParam: 1,
    getNextPageParam: pageSuivante,
  });
}
