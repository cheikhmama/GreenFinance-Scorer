/**
 * Forme d'erreur renvoyée par toute route de l'API GreenFinance-Scorer — voir
 * ARCHITECTURE.md §4 côté backend (`register_exception_handlers`, appliqué à l'app
 * racine et à `api_app`). Une seule forme, quelle que soit la route ou le code HTTP.
 */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    correlation_id: string | null;
  };
}

/**
 * Exception typée levée par `apiFetch` (shared/api/client.ts) quand la réponse HTTP
 * n'est pas OK. Porte le `code` métier (ex. "invalid_credentials", "not_authenticated")
 * pour permettre à l'appelant de distinguer les cas sans re-parser le corps JSON —
 * voir features/auth/components/LoginPage.tsx pour un exemple d'utilisation.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly correlationId: string | null;

  constructor(status: number, body: ApiErrorBody) {
    super(body.error.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.error.code;
    this.correlationId = body.error.correlation_id;
  }
}
