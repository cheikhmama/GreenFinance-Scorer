import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ScoreWaterfall } from "./ScoreWaterfall";

const ID = "66666666-6666-6666-6666-666666666666";
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function explication(requested: string, used: string) {
  return {
    report_id: ID,
    company_id: ID,
    config_version: 2,
    config_hash: "a".repeat(64),
    score: 62.5,
    baseline_score: 50,
    coverage_rate: 0.6,
    baseline: { requested, used, sector: used === "SECTOR" ? "Énergie" : null, peer_count: 4 },
    pillars: [
      { pillar: "ENVIRONNEMENT", contribution: 15 },
      { pillar: "GOUVERNANCE", contribution: -2.5 },
    ],
    contributions: [
      {
        pillar: "ENVIRONNEMENT",
        metric_code: "part_renouvelable_pourcentage",
        value: 80,
        normalized_value: 80,
        baseline_value: 50,
        effective_weight: 0.5,
        contribution: 15,
      },
      {
        pillar: "GOUVERNANCE",
        metric_code: "femmes_conseil_pourcentage",
        value: 20,
        normalized_value: 40,
        baseline_value: null,
        effective_weight: 0.5,
        contribution: -2.5,
      },
    ],
  };
}

function renderChart() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ScoreWaterfall rapportId={ID} />
    </QueryClientProvider>,
  );
}

describe("ScoreWaterfall", () => {
  it("affiche la cascade de la référence au score, pilier par pilier", async () => {
    fetchMock.mockResolvedValue(Response.json(explication("SECTOR", "SECTOR")));
    renderChart();

    expect(
      await screen.findByText("Comparé à 4 entreprise(s) du secteur Énergie."),
    ).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toBe(
      `/api/v1/reports/${ID}/score-explanation?baseline=SECTOR`,
    );
    expect(screen.getByText("Environnement · +15 pts")).toBeInTheDocument();
    expect(screen.getByText("Gouvernance · −2,5 pts")).toBeInTheDocument();
    expect(screen.getByText("+15")).toBeInTheDocument();
    expect(screen.getByText("(aucun pair ne le publie)")).toBeInTheDocument();
    expect(screen.getByText("62,5")).toBeInTheDocument();
  });

  it("signale le repli et recharge avec toutes les entreprises à la demande", async () => {
    fetchMock
      .mockResolvedValueOnce(Response.json(explication("SECTOR", "UNIVERSE")))
      .mockResolvedValueOnce(Response.json(explication("UNIVERSE", "UNIVERSE")));
    const user = userEvent.setup();
    renderChart();

    expect(await screen.findByText(/repli sur toutes les entreprises/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Toutes les entreprises" }));

    expect(fetchMock.mock.calls[1][0]).toBe(
      `/api/v1/reports/${ID}/score-explanation?baseline=UNIVERSE`,
    );
    expect(screen.getByRole("button", { name: "Toutes les entreprises" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });
});
