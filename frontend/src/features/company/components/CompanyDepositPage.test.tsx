import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CompanyDepositPage } from "./CompanyDepositPage";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function renderPage() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}
    >
      <MemoryRouter initialEntries={["/company/deposer"]}>
        <Routes>
          <Route path="/company/deposer" element={<CompanyDepositPage />} />
          <Route path="/company/rapports" element={<h1>Mes rapports</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const pdf = () => new File(["%PDF-1.7"], "rapport-2025.pdf", { type: "application/pdf" });

describe("Espace Entreprise — déposer un rapport", () => {
  it("refuse l’envoi sans fichier, puis dépose et renvoie vers la liste des rapports", async () => {
    fetchMock.mockResolvedValue(Response.json({ id: "r1" }, { status: 201 }));
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Déposer" }));
    expect(await screen.findByText("Un fichier PDF est requis.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();

    await user.selectOptions(screen.getByLabelText("Type de rapport"), "RAPPORT_CLIMAT");
    await user.clear(screen.getByLabelText("Année"));
    await user.type(screen.getByLabelText("Année"), "2025");
    await user.upload(screen.getByLabelText("Fichier PDF"), pdf());
    await user.click(screen.getByRole("button", { name: "Déposer" }));

    expect(await screen.findByRole("heading", { name: "Mes rapports" })).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/company/rapports");
    const corps = init?.body as FormData;
    expect((corps.get("fichier") as File).name).toBe("rapport-2025.pdf");
    expect(corps.get("type")).toBe("RAPPORT_CLIMAT");
    expect(corps.get("annee_reporting")).toBe("2025");
  });

  it("affiche le refus du serveur sans quitter la page", async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        {
          error: {
            code: "rapport_doublon",
            message: "Ce fichier a déjà été déposé.",
            correlation_id: null,
          },
        },
        { status: 422 },
      ),
    );
    const user = userEvent.setup();
    renderPage();

    await user.upload(screen.getByLabelText("Fichier PDF"), pdf());
    await user.click(screen.getByRole("button", { name: "Déposer" }));

    expect(await screen.findByText("Ce fichier a déjà été déposé.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Mes rapports" })).not.toBeInTheDocument();
  });
});
