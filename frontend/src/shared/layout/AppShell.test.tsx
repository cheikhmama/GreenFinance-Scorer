import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RequireRole } from "@/shared/RequireRole";
import { ThemeProvider } from "@/shared/theme/ThemeProvider";
import { ConfirmProvider } from "@/shared/ui/confirm-dialog";
import { AppShell } from "./AppShell";

const getCurrentUser = vi.fn();
const logout = vi.fn();

vi.mock("@/shared/api/generated/auth/auth", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  getCurrentUser: () => getCurrentUser(),
  logout: () => logout(),
}));
vi.mock("@/shared/notifications/NotificationBell", () => ({ NotificationBell: () => null }));

const user = { id: 1, email: "contact@acme.test", name: "Acme", role: "ENTERPRISE", avatar: null };

function renderShell() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [
      {
        path: "/company",
        element: (
          <RequireRole allowedRoles={["ENTERPRISE"]}>
            <AppShell />
          </RequireRole>
        ),
        children: [{ index: true, element: <p>Tableau de bord</p> }],
      },
      { path: "/login", element: <h1>Page de connexion</h1> },
    ],
    { initialEntries: ["/company"] },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ConfirmProvider>
          <RouterProvider router={router} />
        </ConfirmProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

describe("AppShell — déconnexion", () => {
  beforeEach(() => {
    getCurrentUser.mockReset().mockResolvedValue(user);
    logout.mockReset().mockResolvedValue(undefined);
  });

  it("confirme, appelle /auth/logout puis mène à /login", async () => {
    renderShell();

    await userEvent.click(await screen.findByRole("button", { name: "Se déconnecter" }));
    await userEvent.click(await screen.findByRole("button", { name: "Confirmer la déconnexion" }));

    expect(await screen.findByRole("heading", { name: "Page de connexion" })).toBeInTheDocument();
    expect(logout).toHaveBeenCalledTimes(1);
  });
});

describe("AppShell — menu mobile", () => {
  beforeEach(() => {
    getCurrentUser.mockReset().mockResolvedValue(user);
  });

  it("s’ouvre en fenêtre modale, Échap la ferme et rend le focus au bouton", async () => {
    const utilisateur = userEvent.setup();
    renderShell();
    const ouvrir = await screen.findByRole("button", { name: "Ouvrir le menu" });
    expect(ouvrir).toHaveAttribute("aria-expanded", "false");

    await utilisateur.click(ouvrir);
    const menu = await screen.findByRole("dialog", { name: "Menu" });
    expect(ouvrir).toHaveAttribute("aria-expanded", "true");
    expect(menu).toContainElement(document.activeElement as HTMLElement);

    await utilisateur.keyboard("{Escape}");
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "Menu" })).not.toBeInTheDocument(),
    );
    expect(ouvrir).toHaveFocus();
  });
});
