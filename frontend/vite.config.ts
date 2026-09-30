/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
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
