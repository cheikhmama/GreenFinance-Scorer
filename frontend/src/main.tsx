import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { ApiError } from "./shared/api/errors";
import "./index.css";

// Un 400/401/403/404 est un état applicatif (entrée invalide, session absente, accès refusé,
// ressource inexistante), jamais une panne réseau transitoire — le relancer automatiquement ne
// fait que masquer le problème derrière un état de chargement qui ne se résout jamais (voir
// FRONTEND-ARCHITECTURE.md §3.2). Tout autre statut garde le comportement par défaut de
// TanStack Query (3 tentatives).
const STATUTS_SANS_RELANCE = new Set([400, 401, 403, 404]);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) =>
        error instanceof ApiError && STATUTS_SANS_RELANCE.has(error.status)
          ? false
          : failureCount < 3,
    },
  },
});

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("#root introuvable dans index.html");
}

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
