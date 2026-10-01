import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ExtractionRunsCard } from "./ExtractionRunsCard";

const ID = "77777777-7777-7777-7777-777777777777";
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function renderCard() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <ExtractionRunsCard rapportId={ID} />
    </QueryClientProvider>,
  );
}

describe("ExtractionRunsCard", () => {
  it("liste chaque exécution avec son issue et ce qui a produit les valeurs", async () => {
    fetchMock.mockResolvedValue(
      Response.json([
        {
          id: "a",
          started_at: "2026-10-01T10:00:00",
          finished_at: "2026-10-01T10:05:00",
          status: "SUCCEEDED",
          error: null,
          docling_version: "2.119.0",
          llm_model: "gemini-3.6-flash",
          prompt_version: "2026-10-01",
        },
        {
          id: "b",
          started_at: "2026-10-01T09:00:00",
          finished_at: "2026-10-01T09:01:00",
          status: "RETRY_SCHEDULED",
          error: "appel_llm_echoue",
          docling_version: "2.119.0",
          llm_model: "gemini-3.6-flash",
          prompt_version: "2026-10-01",
        },
      ]),
    );
    renderCard();

    expect(await screen.findByText("Réussie")).toBeInTheDocument();
    expect(screen.getByText("Reprise programmée")).toBeInTheDocument();
    expect(screen.getByText("appel_llm_echoue")).toBeInTheDocument();
    expect(screen.getAllByText("gemini-3.6-flash")).toHaveLength(2);
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/v1/admin/reports/${ID}/extraction-runs`);
  });

  it("explique l’absence d’exécution pour un rapport extrait avant le suivi", async () => {
    fetchMock.mockResolvedValue(Response.json([]));
    renderCard();

    expect(await screen.findByText(/Aucune exécution enregistrée/)).toBeInTheDocument();
  });
});
