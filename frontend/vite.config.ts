/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
// Mêmes en-têtes que l'API (app/core/security_headers.py) pour les pages servies par Vite :
// les liens à jeton (/activer-compte, /inscription-entreprise/suivi) ne fuient pas dans le
// Referer, et aucune page ne s'affiche dans un cadre tiers.
const ENTETES_SECURITE = {
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "no-referrer",
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  preview: { headers: ENTETES_SECURITE },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    headers: ENTETES_SECURITE,
    proxy: {
      // Le backend FastAPI pose un cookie httpOnly `access_token`. En développement,
      // le proxy Vite fait apparaître l'API comme same-origin (localhost:5173) plutôt
      // que cross-origin (localhost:8000) : le navigateur envoie/accepte alors le
      // cookie sans configuration CORS ni SameSite particulière côté backend.
      "/api/v1": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
    // userEvent tape caractère par caractère : sous la charge de l'exécution parallèle (et sur les
    // 2 cœurs d'un runner CI), un formulaire long dépasse les 5 s par défaut sans rien avoir de
    // faux — ces dépassements étaient la cause des échecs intermittents (tâche 4.5).
    testTimeout: 15_000,
  },
});
