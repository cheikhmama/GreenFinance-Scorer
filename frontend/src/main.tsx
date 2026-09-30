import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { creerQueryClient } from "./queryClient";
import { ThemeProvider } from "./shared/theme/ThemeProvider";
import { ConfirmProvider } from "./shared/ui/confirm-dialog";
import "./index.css";

const queryClient = creerQueryClient();

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("#root introuvable dans index.html");
}

createRoot(rootElement).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <ConfirmProvider>
          <App />
        </ConfirmProvider>
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
