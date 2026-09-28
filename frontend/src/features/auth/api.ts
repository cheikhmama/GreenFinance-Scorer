import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ApiError } from "@/shared/api/errors";
import {
  changePassword,
  deleteMyAvatar,
  demanderReinitialisationMotDePasse,
  getCurrentUser,
  login,
  logout,
  reinitialiserMotDePasse,
  updateMyProfile,
  uploadMyAvatar,
  verifyMyPassword,
} from "@/shared/api/generated/auth/auth";
import type {
  ChangerMotDePasseRequest,
  DemanderReinitialisationRequest,
  ModifierProfilRequest,
  ReinitialiserMotDePasseRequest,
  VerifierMotDePasseRequest,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import type { LoginRequest, User } from "./schemas";

/** Clé de cache TanStack Query partagée par useCurrentUser, useLogin et useLogout,
 * pour que les trois hooks restent synchronisés sur un seul état de session. */
const CURRENT_USER_QUERY_KEY = ["auth", "me"] as const;

/**
 * GET /auth/me. Sert deux usages : afficher l'utilisateur connecté, et — via
 * `isError`/`isLoading` — déterminer si une session est active. Le cookie httpOnly
 * n'étant pas lisible en JS, interroger cette route est le seul moyen fiable de le
 * savoir (voir shared/RequireRole.tsx et shared/DashboardRedirect.tsx).
 */
export function useCurrentUser() {
  return useQuery<User, ApiError>({
    queryKey: CURRENT_USER_QUERY_KEY,
    queryFn: () => getCurrentUser(),
    // Un 401 est un état applicatif normal (utilisateur déconnecté), pas une panne
    // réseau transitoire : ne pas le masquer derrière des tentatives automatiques.
    retry: false,
  });
}

/** POST /auth/login. En cas de succès, alimente directement le cache de
 * useCurrentUser avec la réponse plutôt que de forcer un refetch de /auth/me. */
export function useLogin() {
  const queryClient = useQueryClient();

  return useMutation<User, ApiError, LoginRequest>({
    mutationFn: (credentials) => login(credentials),
    onSuccess: (user) => {
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, user);
    },
  });
}

/** Demande publique : la réponse ne révèle jamais si le compte existe. */
export function useRequestPasswordReset() {
  return useMutation<void, ApiError, DemanderReinitialisationRequest>({
    mutationFn: (payload) => demanderReinitialisationMotDePasse(payload),
    retry: false,
  });
}

/** Consomme le lien reçu par e-mail, sans ouvrir automatiquement de session. */
export function useResetPassword() {
  return useMutation<void, ApiError, ReinitialiserMotDePasseRequest>({
    mutationFn: (payload) => reinitialiserMotDePasse(payload),
    retry: false,
  });
}

/** POST /auth/logout (204, pas de corps). Vide le cache de useCurrentUser pour que
 * RequireRole redirige immédiatement vers /login sans attendre un refetch. */
export function useLogout() {
  const queryClient = useQueryClient();

  return useMutation<void, ApiError, void>({
    mutationFn: () => logout(),
    onSuccess: () => {
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, undefined);
      queryClient.invalidateQueries({ queryKey: CURRENT_USER_QUERY_KEY });
    },
  });
}

/** PATCH /auth/me — modifie le nom affiché et l'e-mail, jamais le rôle (voir
 * app/auth/schemas.py::ModifierProfilRequest). Écrit directement le résultat dans le cache de
 * useCurrentUser, comme useLogin, plutôt que de forcer un refetch. */
export function useUpdateMyProfile() {
  const queryClient = useQueryClient();

  return useMutation<User, ApiError, ModifierProfilRequest>({
    mutationFn: (payload) => updateMyProfile(payload),
    onSuccess: (user) => {
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, user);
    },
  });
}

/** POST /auth/me/avatar (multipart) — remplace l'avatar existant s'il y en avait déjà un. */
export function useUploadAvatar() {
  const queryClient = useQueryClient();

  return useMutation<User, ApiError, File>({
    mutationFn: (fichier) => uploadMyAvatar({ fichier }),
    onSuccess: (user) => {
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, user);
    },
  });
}

/** DELETE /auth/me/avatar — retour à l'avatar par défaut (initiales). */
export function useDeleteAvatar() {
  const queryClient = useQueryClient();

  return useMutation<User, ApiError, void>({
    mutationFn: () => deleteMyAvatar(),
    onSuccess: (user) => {
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, user);
    },
  });
}

/** POST /auth/verifier-mot-de-passe (204) — étape 1 du changement de mot de passe progressif,
 * ne modifie rien, sert uniquement à afficher une erreur au bon endroit avant l'étape 2. */
export function useVerifyPassword() {
  return useMutation<void, ApiError, VerifierMotDePasseRequest>({
    mutationFn: (payload) => verifyMyPassword(payload),
  });
}

/** POST /auth/changer-mot-de-passe — parcours volontaire depuis le Profil. La réponse pose
 * une nouvelle session : on l'écrit directement dans le cache, comme useLogin, plutôt que de
 * forcer un refetch de /auth/me. */
export function useChangePassword() {
  const queryClient = useQueryClient();

  return useMutation<User, ApiError, ChangerMotDePasseRequest>({
    mutationFn: (payload) => changePassword(payload),
    onSuccess: (user) => {
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, user);
    },
  });
}
