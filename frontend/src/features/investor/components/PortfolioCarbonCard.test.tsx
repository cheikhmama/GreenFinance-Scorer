import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PortfolioCarbonCard } from "./PortfolioCarbonCard";

const ID = "44444444-4444-4444-4444-444444444444";
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function position(excluded_reason: string | null) {
  return {
    position_id: crypto.randomUUID(),
    company_id: null,
    company_name: null,
    identifier: null,
    amount: 1000,
    attribution_factor: null,
    financed_emissions_scope_1_2: null,
    financed_emissions_scope_3: null,
    carbon_intensity: null,
    data_quality: null,
    emissions_year: null,
    scope_2_basis: null,
    enterprise_value_as_of: null,
    excluded_reason,
  };
}

function renderCard() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <PortfolioCarbonCard portefeuilleId={ID} />
    </QueryClientProvider>,
  );
}

describe("PortfolioCarbonCard", () => {
  it("affiche chaque indicateur avec sa couverture, et les motifs d’exclusion", async () => {
    fetchMock.mockResolvedValue(
      Response.json({
        portfolio_id: ID,
        currency: "USD",
        total_value: 3000,
        financed_emissions_scope_1_2: 13.9,
        financed_emissions_scope_3: null,
        carbon_footprint_scope_1_2: 13.9,
        waci_scope_1_2: 7.5,
        data_quality_scope_1_2: 3,
        data_quality_scope_3: null,
        coverage_scope_1_2: 1 / 3,
        coverage_scope_3: 0,
        coverage_waci: 1 / 3,
        positions: [
          position(null),
          position("MISSING_EVIC"),
          position("UNMATCHED"),
          position("UNMATCHED"),
        ],
      }),
    );
    renderCard();

    expect(await screen.findByText("13,9 tCO₂e")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/v1/portfolios/${ID}/carbon`);
    // Scope 3 absent : un tiret, jamais « 0 tCO₂e ».
    expect(screen.getByText("Émissions financées, Scope 3 (à part)").nextSibling).toHaveTextContent(
      "—",
    );
    expect(screen.getByText("7,5 tCO₂e / M USD de CA")).toBeInTheDocument();
    expect(screen.getByText("3 / 5")).toBeInTheDocument();
    expect(screen.getAllByText("Couverture 33 %")).toHaveLength(3);
    expect(screen.getByText("2 × ligne importée non rapprochée")).toBeInTheDocument();
    expect(screen.getByText("1 × EVIC non renseignée")).toBeInTheDocument();
  });
});
