import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  companyKeys,
  DELAI_SUIVI_ANALYSE_MS,
  useActualisationSurNotification,
  useCompanyReports,
} from "./api";

const fetchMock = vi.fn<typeof fetch>();

function ligne(status: string) {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    company_id: "c",
    type: "RAPPORT_ESG",
    channel: "ENTREPRISE",
    created_at: "2026-09-01T08:00:00Z",
    submitted_at: null,
    status,
    source_file: "x.pdf",
    original_filename: "x.pdf",
    fiscal_year: 2025,
    extraction_finished_at: null,
    extraction_error: null,
    extraction_attempts: 0,
    version: 1,
    previous_report_id: null,
    checksum_sha256: null,
    synthesis_available: false,
  };
}

function enveloppe(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

function appelsListe() {
  return fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/company/rapports")).length;
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useCompanyReports", () => {
  it("se rafraîchit tant qu’une analyse tourne, puis s’arrête", async () => {
    const reponses = [[ligne("EXTRACTING")], [ligne("DRAFT")]];
    fetchMock.mockImplementation(async () => Response.json(reponses.shift() ?? [ligne("DRAFT")]));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useCompanyReports(), { wrapper: enveloppe(client) });
    await waitFor(() => expect(result.current.data?.[0].status).toBe("EXTRACTING"));

    await vi.advanceTimersByTimeAsync(DELAI_SUIVI_ANALYSE_MS);
    await waitFor(() => expect(result.current.data?.[0].status).toBe("DRAFT"));
    const apres = appelsListe();

    await vi.advanceTimersByTimeAsync(DELAI_SUIVI_ANALYSE_MS * 3);
    expect(appelsListe()).toBe(apres);
  });
});

describe("useActualisationSurNotification", () => {
  function compteur(total: number) {
    return Response.json({ items: [], total, page: 1, page_size: 1, pages: 1 });
  }

  it("invalide les déclarations quand le nombre de non-lues augmente, pas quand il baisse", async () => {
    const totaux = [1, 2, 0];
    fetchMock.mockImplementation(async () => compteur(totaux.shift() ?? 0));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalider = vi.spyOn(client, "invalidateQueries");
    renderHook(() => useActualisationSurNotification(), { wrapper: enveloppe(client) });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(invalider).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(60_000); // 1 → 2
    await waitFor(() =>
      expect(invalider).toHaveBeenCalledWith({ queryKey: companyKeys.reports() }),
    );
    invalider.mockClear();

    await vi.advanceTimersByTimeAsync(60_000); // 2 → 0
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(invalider).not.toHaveBeenCalled();
  });
});
