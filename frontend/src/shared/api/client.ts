import { ApiError, type ApiErrorBody } from "./errors";

const API_BASE_URL = "/api/v1";

// Double-soumission CSRF (app/auth/csrf.py) : le cookie __Host-csrf_token est délibérément
// lisible en JS (httponly=False, voir app/auth/router.py::_ouvrir_session) pour être recopié
// ici dans l'en-tête X-CSRF-Token sur toute requête mutante — le backend compare les deux.
const CSRF_COOKIE_NAME = "__Host-csrf_token";
const CSRF_HEADER_NAME = "X-CSRF-Token";
const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function readCsrfCookie(): string | null {
  const prefix = `${CSRF_COOKIE_NAME}=`;
  for (const part of document.cookie.split("; ")) {
    if (part.startsWith(prefix)) {
      return decodeURIComponent(part.slice(prefix.length));
    }
  }
  return null;
}

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
  // FormData (dépôt de fichier, ex. features/company) : jamais de Content-Type manuel — fetch
  // doit fixer lui-même "multipart/form-data; boundary=..." à partir du corps, un en-tête forcé
  // à "application/json" romprait silencieusement l'upload côté serveur.
  const isFormData = init.body instanceof FormData;
  const method = (init.method ?? "GET").toUpperCase();
  const csrfToken = MUTATING_METHODS.has(method) ? readCsrfCookie() : null;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init.body && !isFormData ? { "Content-Type": "application/json" } : {}),
      ...(csrfToken !== null ? { [CSRF_HEADER_NAME]: csrfToken } : {}),
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
