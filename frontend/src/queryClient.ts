import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { gererSessionPerdue } from "./features/auth/session";
import { ApiError } from "./shared/api/errors";

// Un 400/401/403/404 est un état applicatif (entrée invalide, session absente, accès refusé,
// ressource inexistante), jamais une panne réseau transitoire — le relancer automatiquement ne
// fait que masquer le problème derrière un état de chargement qui ne se résout jamais (voir
// FRONTEND-ARCHITECTURE.md §3.2). Tout autre statut garde le comportement par défaut de
// TanStack Query (3 tentatives).
const STATUTS_SANS_RELANCE = new Set([400, 401, 403, 404]);

// Session expirée ou révoquée pendant l'utilisation (tâche 4.3) : retour à la connexion, quelle
// que soit la requête qui l'a découvert (voir features/auth/session.ts).
export function creerQueryClient(): QueryClient {
  const queryClient: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => gererSessionPerdue(queryClient, error, query.queryKey),
    }),
    mutationCache: new MutationCache({
      onError: (error) => gererSessionPerdue(queryClient, error),
    }),
    defaultOptions: {
      queries: {
        retry: (failureCount, error) =>
          error instanceof ApiError && STATUTS_SANS_RELANCE.has(error.status)
            ? false
            : failureCount < 3,
      },
    },
  });
  return queryClient;
}
