import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { StrictMode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConfirmEmailChangePage } from "./ConfirmEmailChangePage";

const TOKEN = "c".repeat(43);
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function renderPage(query = `?token=${TOKEN}`) {
  return render(
    <StrictMode>
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={[`/confirmer-email${query}`]}>
          <ConfirmEmailChangePage />
        </MemoryRouter>
      </QueryClientProvider>
    </StrictMode>,
  );
}

describe("ConfirmEmailChangePage", () => {
  it("confirme une seule fois, même sous StrictMode, et affiche la nouvelle adresse", async () => {
    fetchMock.mockResolvedValue(Response.json({ id: "u", email: "nouvelle@example.com" }));
    renderPage();

    // Le paragraphe de chargement porte déjà role="status" : attendre le message final lui-même.
    expect(await screen.findByText("Adresse mise à jour")).toBeInTheDocument();
    expect(screen.getByText(/Utilisez nouvelle@example.com/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith(
      "/api/v1/auth/confirmer-changement-email",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ token: TOKEN }) }),
    );
  });

  it("n’appelle pas l’API pour un lien mal formé", () => {
    renderPage("?token=incomplet");

    expect(screen.getByRole("alert")).toHaveTextContent("absent ou incomplet");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("explique qu’une adresse déjà prise laisse l’adresse actuelle inchangée", async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        { error: { code: "email_deja_utilise", message: "detail", correlation_id: null } },
        { status: 422 },
      ),
    );
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("déjà utilisée par un autre compte");
  });
});
