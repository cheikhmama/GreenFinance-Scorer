import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { InstitutionDashboardPage } from "./InstitutionDashboardPage";

const fetchMock = vi.fn<typeof fetch>();

const ANALYSES = [
  {
    id: "a1",
    researcher_id: "r1",
    title: "Mines et industrie",
    status: "SOUMISE",
    version: 2,
    created_at: "2026-10-01T10:00:00Z",
    submitted_at: "2026-10-02T10:00:00Z",
    project_id: "p1",
    project_name: "Intensité carbone",
  },
  {
    id: "a2",
    researcher_id: "r1",
    title: "Brouillon interne",
    status: "BROUILLON",
    version: 1,
    created_at: "2026-10-01T10:00:00Z",
    submitted_at: null,
    project_id: "p1",
    project_name: "Intensité carbone",
  },
];

const PROJETS = [
  {
    id: "p1",
    institution_id: "i1",
    name: "Intensité carbone",
    description: null,
    objective: null,
    start_date: null,
    planned_end_date: null,
    deadline: "2026-11-30",
    status: "OUVERT",
    created_at: "2026-09-01T10:00:00Z",
    closed_at: null,
  },
];

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (url) => {
    const u = String(url);
    if (u.includes("/institution/analyses")) return Response.json(ANALYSES);
    if (u.includes("/institution/projets")) return Response.json(PROJETS);
    return Response.json([]);
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("Institution — tableau de bord", () => {
  it("liste les analyses à décider et les projets avec leur échéance", async () => {
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter>
          <InstitutionDashboardPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const decider = await screen.findByRole("link", { name: "Mines et industrie" });
    expect(decider).toHaveAttribute("href", "/institution/analyses/a1");
    // Seules les analyses soumises attendent une décision.
    expect(screen.queryByText("Brouillon interne")).not.toBeInTheDocument();
    const projet = screen.getAllByRole("link", { name: "Intensité carbone" })[0];
    expect(projet).toHaveAttribute("href", "/institution/projets/p1");
    expect(
      within(projet.closest("li") as HTMLElement).getByText(/Échéance le 30\/11\/2026/),
    ).toBeInTheDocument();
  });
});
