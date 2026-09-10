import type { UseQueryResult } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import * as authApi from "@/features/auth/api";
import type { User } from "@/features/auth/schemas";
import type { ApiError } from "@/shared/api/errors";
import { RequireRole } from "./RequireRole";

vi.mock("@/features/auth/api", () => ({
  useCurrentUser: vi.fn(),
}));

function renderProtectedRoute(mockResult: Partial<UseQueryResult<User, ApiError>>) {
  vi.mocked(authApi.useCurrentUser).mockReturnValue(mockResult as UseQueryResult<User, ApiError>);

  return render(
    <MemoryRouter initialEntries={["/protected"]}>
      <Routes>
        <Route path="/login" element={<div>Page de connexion</div>} />
        <Route
          path="/protected"
          element={
            <RequireRole allowedRoles={["ADMINISTRATEUR"]}>
              <div>Contenu protégé</div>
            </RequireRole>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RequireRole", () => {
  it("redirige vers /login si GET /auth/me échoue (pas de session)", () => {
    renderProtectedRoute({ data: undefined, isLoading: false, isError: true });

    expect(screen.getByText("Page de connexion")).toBeInTheDocument();
  });

  it("affiche un message si le rôle de l'utilisateur connecté n'est pas autorisé", () => {
    renderProtectedRoute({
      data: {
        id: "1",
        email: "entreprise@example.com",
        nom: "Entreprise Test",
        role: "ENTREPRISE",
        date_creation: "",
        actif: true,
        doit_changer_mot_de_passe: false,
      },
      isLoading: false,
      isError: false,
    });

    expect(screen.getByText("Accès non autorisé")).toBeInTheDocument();
  });

  it("affiche le contenu protégé si le rôle correspond", () => {
    renderProtectedRoute({
      data: {
        id: "1",
        email: "admin@example.com",
        nom: "Admin Test",
        role: "ADMINISTRATEUR",
        date_creation: "",
        actif: true,
        doit_changer_mot_de_passe: false,
      },
      isLoading: false,
      isError: false,
    });

    expect(screen.getByText("Contenu protégé")).toBeInTheDocument();
  });
});
