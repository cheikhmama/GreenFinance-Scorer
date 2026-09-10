import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ApiError } from "@/shared/api/errors";
import { changePassword, getCurrentUser, login, logout } from "@/shared/api/generated/auth/auth";
import type { ChangerMotDePasseRequest } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
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

/** POST /auth/changer-mot-de-passe — accessible même quand doit_changer_mot_de_passe
 * bloque le reste de l'API (voir app/core/dependencies.py). La réponse pose une
 * nouvelle session (doit_changer_mot_de_passe désormais faux) : on l'écrit directement
 * dans le cache, comme useLogin, plutôt que de forcer un refetch de /auth/me. */
export function useChangePassword() {
  const queryClient = useQueryClient();

  return useMutation<User, ApiError, ChangerMotDePasseRequest>({
    mutationFn: (payload) => changePassword(payload),
    onSuccess: (user) => {
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, user);
    },
  });
}
