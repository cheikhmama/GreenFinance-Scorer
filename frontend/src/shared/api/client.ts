import { ApiError, type ApiErrorBody } from "./errors";

const API_BASE_URL = "/api/v1";

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as { error: unknown }).error === "object"
  );
}

/**
 * Client HTTP fin partagé par tous les modules `features/*`.
 *
 * Statut : Auth MVP — Étape 9 partielle. Exception transitoire documentée dans
 * FRONTEND-ARCHITECTURE.md §3.1 : pas de génération OpenAPI pour l'instant, ce
 * client fetch écrit à la main reste limité à `features/auth`. Il est retiré et
 * remplacé par le client généré Orval dès les premières routes métier
 * (admin/company/audit/investor/researcher/institution).
 *
 * `credentials: "include"` est systématique : le backend pose un cookie httpOnly
 * (`access_token`) que le JavaScript ne peut ni lire ni écrire, donc chaque requête
 * doit explicitement demander au navigateur de le joindre.
 */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });

  // 204 No Content (ex. logout) : pas de corps JSON à parser.
  if (response.status === 204) {
    return undefined as T;
  }

  const body: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    if (isApiErrorBody(body)) {
      throw new ApiError(response.status, body);
    }
    // Filet de sécurité si l'API renvoie un jour une erreur hors du format
    // {"error": {...}} (ex. 502 d'un proxy intermédiaire) : on ne masque jamais
    // silencieusement un échec HTTP.
    throw new ApiError(response.status, {
      error: {
        code: "unexpected_response",
        message: response.statusText || "Réponse inattendue du serveur",
        correlation_id: null,
      },
    });
  }

  return body as T;
}
