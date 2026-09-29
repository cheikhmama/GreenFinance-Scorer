import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConfirmProvider } from "@/shared/ui/confirm-dialog";
import { OnboardingPanel } from "./OnboardingPanel";

const ID = "11111111-1111-1111-1111-111111111111";
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function renderPanel() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <ConfirmProvider>
        <MemoryRouter initialEntries={[`/admin/entreprises/${ID}`]}>
          <Routes>
            <Route
              path="/admin/entreprises/:id"
              element={<OnboardingPanel entrepriseId={ID} nom="Minière du Nord" />}
            />
            <Route path="/admin/entreprises" element={<h1>Liste des entreprises</h1>} />
          </Routes>
        </MemoryRouter>
      </ConfirmProvider>
    </QueryClientProvider>,
  );
}

describe("OnboardingPanel", () => {
  it("valide après confirmation", async () => {
    fetchMock.mockResolvedValue(
      Response.json({ company_id: ID, decision: "approve", status: "ACTIVE", onboarded_at: null }),
    );
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByRole("button", { name: /Valider l’inscription/ }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Valider" }));

    expect(fetchMock).toHaveBeenCalledExactlyOnceWith(
      `/api/v1/admin/companies/${ID}/onboard`,
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ decision: "approve" }) }),
    );
  });

  it("exige un motif pour refuser, l’envoie, puis revient à la liste", async () => {
    fetchMock.mockResolvedValue(
      Response.json({ company_id: ID, decision: "reject", status: null, onboarded_at: null }),
    );
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByRole("button", { name: /Refuser/ }));
    const confirmer = screen.getByRole("button", { name: "Confirmer le refus" });
    expect(confirmer).toBeDisabled();
    await user.type(screen.getByLabelText(/Motif du refus/), "Entreprise introuvable au registre.");
    await user.click(confirmer);

    expect(await screen.findByRole("heading", { name: "Liste des entreprises" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith(
      `/api/v1/admin/companies/${ID}/onboard`,
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ decision: "reject", reason: "Entreprise introuvable au registre." }),
      }),
    );
  });
});
