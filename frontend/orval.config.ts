import { defineConfig } from "orval";

/**
 * Génère des fonctions et types TypeScript typés depuis openapi.json — jamais des hooks
 * TanStack Query tout faits : chaque feature écrit ses propres hooks au-dessus de ces
 * fonctions (voir features/auth/api.ts), pour garder la main sur les query keys et les
 * effets de cache (FRONTEND-ARCHITECTURE.md §3.1).
 *
 * Le mutator (`apiFetch`, shared/api/client.ts) reste l'unique point de transport :
 * credentials, en-tête CSRF (X-CSRF-Token, double soumission depuis __Host-csrf_token),
 * décodage de l'erreur standard, correlation_id.
 */
export default defineConfig({
  greenfinance: {
    input: "./openapi.json",
    output: {
      mode: "tags-split",
      target: "src/shared/api/generated",
      client: "fetch",
      httpClient: "fetch",
      clean: true,
      indexFiles: true,
      override: {
        mutator: {
          path: "src/shared/api/client.ts",
          name: "apiFetch",
        },
        fetch: {
          // apiFetch<T> renvoie directement le corps parsé (Promise<T>), jamais une
          // enveloppe {data, status, headers} — désactivé pour que les types générés
          // reflètent ce que la fonction renvoie réellement à l'exécution.
          includeHttpResponseReturnType: false,
        },
      },
    },
  },
});
