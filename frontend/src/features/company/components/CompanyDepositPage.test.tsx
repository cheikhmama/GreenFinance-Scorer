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
          <Route path="/company/rapports/:rapportId" element={<h1>Brouillon ouvert</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Espace Entreprise — ouvrir une déclaration", () => {
  it("ouvre un brouillon pour le type et l’exercice choisis, puis mène à sa page", async () => {
    fetchMock.mockResolvedValue(Response.json({ id: "r1" }, { status: 201 }));
    const user = userEvent.setup();
    renderPage();

    await user.selectOptions(screen.getByLabelText("Type de rapport"), "RAPPORT_CLIMAT");
    await user.clear(screen.getByLabelText("Exercice"));
    await user.type(screen.getByLabelText("Exercice"), "2024");
    await user.click(screen.getByRole("button", { name: "Ouvrir la déclaration" }));

    expect(await screen.findByRole("heading", { name: "Brouillon ouvert" })).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/reports");
    expect(JSON.parse(init?.body as string)).toEqual({
      report_type: "RAPPORT_CLIMAT",
      fiscal_year: 2024,
    });
  });

  it("refuse un exercice futur et affiche le refus du serveur sans quitter la page", async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        {
          error: {
            code: "brouillon_existant",
            message: "Une déclaration est déjà ouverte pour cet exercice et ce type de rapport.",
            correlation_id: null,
          },
        },
        { status: 422 },
      ),
    );
    const user = userEvent.setup();
    renderPage();

    await user.clear(screen.getByLabelText("Exercice"));
    await user.type(screen.getByLabelText("Exercice"), String(new Date().getFullYear() + 1));
    await user.click(screen.getByRole("button", { name: "Ouvrir la déclaration" }));
    expect(
      await screen.findByText("L'exercice ne peut pas être postérieur à l'année en cours."),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();

    await user.clear(screen.getByLabelText("Exercice"));
    await user.type(screen.getByLabelText("Exercice"), "2024");
    await user.click(screen.getByRole("button", { name: "Ouvrir la déclaration" }));

    expect(
      await screen.findByText(
        "Une déclaration est déjà ouverte pour cet exercice et ce type de rapport.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Brouillon ouvert" })).not.toBeInTheDocument();
  });
});
