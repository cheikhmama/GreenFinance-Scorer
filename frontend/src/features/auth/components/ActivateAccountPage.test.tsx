import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ActivateAccountPage } from "./ResetPasswordPage";

const TOKEN = "b".repeat(43);
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function renderPage(query = `?token=${TOKEN}`) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[`/activer-compte${query}`]}>
        <Routes>
          <Route path="/activer-compte" element={<ActivateAccountPage />} />
          <Route path="/dashboard" element={<h1>Espace de l’utilisateur</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function submitPassword(password: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Nouveau mot de passe", { selector: "input" }), password);
  await user.type(screen.getByLabelText("Confirmer le mot de passe"), password);
  await user.click(screen.getByRole("button", { name: "Enregistrer le mot de passe" }));
}

describe("ActivateAccountPage", () => {
  it("pose le premier mot de passe puis ouvre l’espace du rôle (via /dashboard)", async () => {
    fetchMock.mockResolvedValue(
      Response.json({ id: "u1", email: "a@b.mr", role: "INVESTOR", name: null, avatar: null }),
    );
    renderPage();
    await submitPassword("premier-secret");

    expect(
      await screen.findByRole("heading", { name: "Espace de l’utilisateur" }),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith(
      "/api/v1/auth/activer-compte",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ token: TOKEN, new_password: "premier-secret" }),
      }),
    );
  });

  it("suit les critères du mot de passe pendant la saisie", async () => {
    renderPage();
    const user = userEvent.setup();
    const criteres = screen.getByRole("list", { name: "Critères du mot de passe" });
    expect(criteres).toHaveTextContent("12 caractères au moins (requis) : non rempli");

    await user.type(
      screen.getByLabelText("Nouveau mot de passe", { selector: "input" }),
      "Secret-2026!",
    );
    expect(criteres).toHaveTextContent("12 caractères au moins (requis) : rempli");
    expect(screen.getByText("Robustesse : fort")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Confirmer le mot de passe"), "Secret-2026!");
    expect(criteres).toHaveTextContent("Les deux saisies correspondent : rempli");
  });

  it("applique la règle des 12 caractères sans appel API", async () => {
    renderPage();
    await submitPassword("court-11car");

    expect(await screen.findByText("12 caractères minimum")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("oriente vers l’équipe quand le lien a expiré (pas de renouvellement en libre-service)", async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        { error: { code: "jeton_invalide", message: "detail", correlation_id: null } },
        { status: 422 },
      ),
    );
    renderPage();
    await submitPassword("premier-secret");

    expect(await screen.findByRole("alert")).toHaveTextContent("renvoyer une invitation");
    expect(screen.getByRole("link", { name: "Contacter l’équipe" })).toHaveAttribute(
      "href",
      "/contact",
    );
  });
});
