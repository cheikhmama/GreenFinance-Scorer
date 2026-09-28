import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ApiError } from "@/shared/api/errors";
import type { NotificationPublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { listMyNotifications, markNotificationRead } from "@/shared/api/generated/notifications/notifications";

const NOTIFICATIONS_KEY = ["notifications"] as const;

/** GET /notifications — commun à tous les rôles (voir app/core/router.py, Notification
 * n'appartient à aucun espace acteur), jamais dupliqué par feature. */
export function useMyNotifications(pageSize = 5) {
  return useQuery<NotificationPublic[], ApiError>({
    queryKey: [...NOTIFICATIONS_KEY, "recentes", pageSize],
    queryFn: async () => {
      const page = await listMyNotifications({ page: 1, page_size: pageSize });
      return page.items;
    },
  });
}

/** Compteur non lues, pour le point rouge de NotificationBell — rafraîchi périodiquement pour
 * qu'un événement survenu pendant que l'utilisateur est sur la plateforme finisse par apparaître
 * sans recharger la page. */
export function useUnreadNotificationsCount() {
  return useQuery<number, ApiError>({
    queryKey: [...NOTIFICATIONS_KEY, "non-lues-total"],
    queryFn: async () => {
      const page = await listMyNotifications({ non_lues_seulement: true, page: 1, page_size: 1 });
      return page.total;
    },
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });
}

/** POST /notifications/{id}/lu. Invalide le compteur et les listes affichées pour que le point
 * rouge et les lignes « non lue » se mettent à jour immédiatement. */
export function useMarkNotificationRead() {
  const queryClient = useQueryClient();

  return useMutation<NotificationPublic, ApiError, string>({
    mutationFn: (notificationId) => markNotificationRead(notificationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
    },
  });
}

// Types dont la cible est un élément précis (id_ressource requis) — voir app/core/notifications.py
// pour la liste des types réellement émis côté backend.
const LIENS_AVEC_ID: Record<string, (id: string) => string> = {
  RAPPORT_DEPOSE: (id) => `/company/rapports/${id}`,
  RAPPORT_EXTRACTION_ECHOUEE: (id) => `/company/rapports/${id}`,
  RAPPORT_AFFECTE_ENTREPRISE: (id) => `/company/rapports/${id}`,
  RAPPORT_AVIS_RENDU_ENTREPRISE: (id) => `/company/rapports/${id}`,
  RAPPORT_VALIDE: (id) => `/company/rapports/${id}`,
  RAPPORT_REJETE: (id) => `/company/rapports/${id}`,
  RAPPORT_CORRECTION_DEMANDEE: (id) => `/company/rapports/${id}`,
  RAPPORT_AFFECTE_AUDITEUR: (id) => `/audit/rapports/${id}`,
  RAPPORT_PRET_A_AFFECTER: (id) => `/admin/rapports/${id}`,
  RAPPORT_AVIS_RENDU_ADMIN: (id) => `/admin/rapports/${id}`,
  ANALYSE_VALIDEE: (id) => `/researcher/analyses/${id}`,
  ANALYSE_CORRECTION_DEMANDEE: (id) => `/researcher/analyses/${id}`,
};

// Types dont la cible est une liste, jamais un id précis (ex. une invitation de rattachement).
// ENTREPRISE_PUBLIEE/SUSPENDUE/REACTIVEE pointent vers « Mes rapports », jamais Profil : ce sont
// des événements sur l'activité de dépôt/publication de l'entreprise, pas sur son compte — Profil
// reste réservé à la gestion du compte (nom, e-mail, mot de passe), jamais une cible de
// notification métier.
const LIENS_FIXES: Record<string, string> = {
  ENTREPRISE_PUBLIEE: "/company/rapports",
  ENTREPRISE_SUSPENDUE: "/company/rapports",
  ENTREPRISE_REACTIVEE: "/company/rapports",
  RATTACHEMENT_INVITATION: "/researcher/rattachements",
  RATTACHEMENT_ACCEPTE: "/institution/chercheurs",
  RATTACHEMENT_REFUSE: "/institution/chercheurs",
};

/** Résout la page vers laquelle un clic sur une notification doit rediriger — null si le type
 * n'est pas reconnu ou si un id_ressource requis est absent (jamais un lien cassé). */
export function resolveNotificationLink(type: string, idRessource: string | null): string | null {
  if (type in LIENS_FIXES) return LIENS_FIXES[type];
  const construireLien = LIENS_AVEC_ID[type];
  if (!construireLien || !idRessource) return null;
  return construireLien(idRessource);
}
