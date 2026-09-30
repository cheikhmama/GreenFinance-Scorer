import { QueryClientProvider, useQuery } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { creerQueryClient } from "@/queryClient";
import { apiFetch } from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { RequireRole } from "@/shared/RequireRole";
import { estSessionPerdue, pageDeRetour } from "./session";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function erreur(status: number, code: string) {
  return new ApiError(status, { error: { code, message: "", correlation_id: null } });
}

function reponse401(code: string) {
  return Response.json({ error: { code, message: "", correlation_id: null } }, { status: 401 });
}

const UTILISATEUR = {
  id: "1",
  email: "a@example.com",
  name: "A",
  avatar: null,
  role: "INVESTOR",
  created_at: "2026-01-01T00:00:00",
  active: true,
  activated_at: null,
};

describe("session perdue", () => {
  it("ne confond jamais un mauvais mot de passe avec une session expirée", () => {
    expect(estSessionPerdue(erreur(401, "not_authenticated"))).toBe(true);
    expect(estSessionPerdue(erreur(401, "session_revoked"))).toBe(true);
    expect(estSessionPerdue(erreur(401, "invalid_token"))).toBe(true);
    expect(estSessionPerdue(erreur(401, "invalid_credentials"))).toBe(false);
    expect(estSessionPerdue(erreur(403, "forbidden"))).toBe(false);
  });

  it("ne rouvre après connexion que des chemins internes", () => {
    expect(pageDeRetour({ depuis: "/investor/portefeuilles?x=1" })).toBe(
      "/investor/portefeuilles?x=1",
    );
    expect(pageDeRetour({ depuis: "//evil.example/x" })).toBeNull();
    expect(pageDeRetour({ depuis: "https://evil.example" })).toBeNull();
    expect(pageDeRetour(null)).toBeNull();
  });

  it("renvoie vers la connexion, page d’origine retenue, quand une requête découvre l’expiration", async () => {
    fetchMock.mockImplementation(async (url) => {
      const chemin = String(url);
      if (chemin.endsWith("/auth/me")) {
        // Connecté au premier chargement, plus du tout ensuite.
        return fetchMock.mock.calls.filter(([u]) => String(u).endsWith("/auth/me")).length === 1
          ? Response.json(UTILISATEUR)
          : reponse401("not_authenticated");
      }
      return reponse401("session_revoked");
    });

    function Ecran() {
      useQuery({ queryKey: ["investor", "donnees"], queryFn: () => apiFetch("/investor/donnees") });
      return <p>Écran protégé</p>;
    }
    function Connexion() {
      const location = useLocation();
      return <p>Connexion depuis {(location.state as { depuis: string }).depuis}</p>;
    }

    render(
      <QueryClientProvider client={creerQueryClient()}>
        <MemoryRouter initialEntries={["/investor/portefeuilles?onglet=2"]}>
          <Routes>
            <Route
              path="/investor/portefeuilles"
              element={
                <RequireRole allowedRoles={["INVESTOR"]}>
                  <Ecran />
                </RequireRole>
              }
            />
            <Route path="/login" element={<Connexion />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText("Connexion depuis /investor/portefeuilles?onglet=2"),
    ).toBeInTheDocument();
    // /auth/me relu une seule fois après l'expiration : pas de boucle.
    expect(fetchMock.mock.calls.filter(([u]) => String(u).endsWith("/auth/me"))).toHaveLength(2);
  });
});
