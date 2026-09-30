import type { QueryClient, QueryKey } from "@tanstack/react-query";
import { ApiError } from "@/shared/api/errors";
import { CURRENT_USER_QUERY_KEY } from "./api";

/** Codes 401 qui signifient « plus de session » (app/core/dependencies.py, app/auth/revocation.py)
 * — jamais `invalid_credentials`, la réponse normale à un mauvais mot de passe (connexion,
 * vérification avant une action sensible), que la page concernée affiche elle-même. */
const CODES_SESSION_PERDUE = new Set(["not_authenticated", "invalid_token", "session_revoked"]);

export function estSessionPerdue(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401 && CODES_SESSION_PERDUE.has(error.code);
}

function estRequeteSession(cle: QueryKey | undefined): boolean {
  return (
    cle !== undefined &&
    cle[0] === CURRENT_USER_QUERY_KEY[0] &&
    cle[1] === CURRENT_USER_QUERY_KEY[1]
  );
}

/** Gestion globale du 401 (tâche 4.3), branchée sur le QueryCache et le MutationCache (main.tsx) :
 * une session expirée ou révoquée au milieu d'un écran relit GET /auth/me, qui échoue à son tour ;
 * <RequireRole> renvoie alors vers /login en retenant la page d'origine. Une erreur de /auth/me
 * elle-même est l'état « déconnecté » normal : l'ignorer évite une boucle de relectures. */
export function gererSessionPerdue(queryClient: QueryClient, error: unknown, cle?: QueryKey): void {
  if (!estSessionPerdue(error) || estRequeteSession(cle)) return;
  void queryClient.resetQueries({ queryKey: CURRENT_USER_QUERY_KEY });
}

/** Page à rouvrir après connexion : chemin interne seulement (jamais une URL absolue ou
 * « //hote », qui ferait de la connexion une redirection ouverte). */
export function pageDeRetour(etat: unknown): string | null {
  const depuis = (etat as { depuis?: unknown } | null)?.depuis;
  if (typeof depuis !== "string" || !depuis.startsWith("/") || depuis.startsWith("//")) {
    return null;
  }
  return depuis;
}
