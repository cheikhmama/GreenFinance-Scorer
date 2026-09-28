import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "./LoginPage";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function renderLoginPage() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<h1>Espace connecté</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LoginPage", () => {
  it("affiche les champs e-mail et mot de passe ainsi que le bouton de connexion", () => {
    renderLoginPage();

    expect(screen.getByLabelText("E-mail")).toBeInTheDocument();
    expect(screen.getByLabelText("Mot de passe")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Se connecter" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Mot de passe oublié ?" })).toHaveAttribute("href", "/mot-de-passe-oublie");
    expect(screen.getByRole("link", { name: "Contactez-nous" })).toHaveAttribute("href", "/contact");
    expect(screen.getByRole("link", { name: "GreenFinance-Scorer — connexion" }).querySelector("img")).toHaveAttribute("src", "/favicon.svg");
  });

  it("permet de vérifier le mot de passe saisi sans soumettre le formulaire", async () => {
    const user = userEvent.setup();
    renderLoginPage();
    const password = screen.getByLabelText("Mot de passe");
    await user.type(password, "mon-secret");
    await user.click(screen.getByRole("button", { name: "Afficher le mot de passe" }));
    expect(password).toHaveAttribute("type", "text");
    expect(password).toHaveValue("mon-secret");
    await user.click(screen.getByRole("button", { name: "Masquer le mot de passe" }));
    expect(password).toHaveAttribute("type", "password");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("valide les champs avant tout appel réseau", async () => {
    const user = userEvent.setup();
    renderLoginPage();
    await user.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(await screen.findByText("L'adresse e-mail est requise")).toBeInTheDocument();
    expect(screen.getByText("Le mot de passe est requis")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    [401, "invalid_credentials", "Adresse e-mail ou mot de passe incorrect."],
    [429, "too_many_requests", "Trop de tentatives de connexion. Veuillez réessayer plus tard."],
    [500, "internal_error", "Une erreur inattendue est survenue. Veuillez réessayer."],
  ])("affiche une erreur adaptée au statut %s", async (status, code, message) => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ error: { code, message: "Détail serveur privé", correlation_id: null } }), { status }));
    const user = userEvent.setup();
    renderLoginPage();
    await user.type(screen.getByLabelText("E-mail"), "membre@example.org");
    await user.type(screen.getByLabelText("Mot de passe"), "mon-secret");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.queryByText("Détail serveur privé")).not.toBeInTheDocument();
  });

  it("ouvre le routeur de tableaux de bord après une connexion réussie", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ id: "utilisateur", role: "INVESTISSEUR" }), { status: 200 }));
    const user = userEvent.setup();
    renderLoginPage();
    await user.type(screen.getByLabelText("E-mail"), "membre@example.org");
    await user.type(screen.getByLabelText("Mot de passe"), "mon-secret");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(await screen.findByRole("heading", { name: "Espace connecté" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith("/api/v1/auth/login", expect.objectContaining({
      method: "POST", credentials: "include", body: JSON.stringify({ email: "membre@example.org", password: "mon-secret" }),
    }));
  });
});
