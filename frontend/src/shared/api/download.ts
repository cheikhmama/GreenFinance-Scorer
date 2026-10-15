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
 * Télécharge un fichier binaire (export CSV) — distinct de apiFetch (shared/api/client.ts), qui
 * parse toujours le corps en JSON et casserait silencieusement sur un contenu CSV. Déclenche le
 * téléchargement navigateur via un lien <a> temporaire, jamais via window.open (bloqué par les
 * popup blockers sur certains navigateurs pour un déclenchement asynchrone).
 */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, { credentials: "include" });

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    if (isApiErrorBody(body)) {
      throw new ApiError(response.status, body);
    }
    throw new ApiError(response.status, {
      error: {
        code: "unexpected_response",
        message: response.statusText || "Téléchargement impossible",
        correlation_id: null,
      },
    });
  }

  enregistrerBlob(await response.blob(), filename);
}

/** Déclenche le téléchargement navigateur d'un contenu déjà en mémoire. Le lien est rattaché au
 * document le temps du clic, et l'URL révoquée après coup : la révoquer aussitôt annule ou casse
 * le téléchargement sous Firefox et Safari. */
export function enregistrerBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
