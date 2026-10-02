import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PendingRegistrationsSection } from "./PendingRegistrationsSection";

const fetchMock = vi.fn<typeof fetch>();

const INSCRIPTION = {
  company_id: "c1",
  company_name: "TEST",
  sector: "Énergie",
  country: "MR",
  status: "PENDING_ONBOARDING",
  registered_at: "2026-10-02T11:15:49Z",
  contact_name: "Mohamed",
  contact_email: "mohamed@exemple.mr",
  tax_id: "12345678",
  tax_id_type: "NIF",
};

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function renderSection() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <PendingRegistrationsSection />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Administration — inscriptions à valider", () => {
  it("liste les demandes et ouvre la fenêtre d’examen", async () => {
    fetchMock.mockImplementation(async (url) =>
      String(url).endsWith("/pending-registrations")
        ? Response.json([INSCRIPTION])
        : Response.json({}, { status: 404 }),
    );
    const user = userEvent.setup();
    renderSection();

    const liste = await screen.findByRole("list", { name: "Inscriptions à valider" });
    expect(within(liste).getByRole("link", { name: "TEST" })).toHaveAttribute(
      "href",
      "/admin/entreprises/c1",
    );
    expect(liste).toHaveTextContent("Énergie · Mauritanie · NIF 12345678");
    expect(liste).toHaveTextContent("Mohamed · mohamed@exemple.mr");

    await user.click(within(liste).getByRole("button", { name: /Examiner/ }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([u]) => String(u).endsWith("/admin/companies/c1/kyc")),
      ).toBe(true),
    );
  });

  it("ne s’affiche pas sans demande en attente", async () => {
    fetchMock.mockImplementation(async () => Response.json([]));
    const { container } = renderSection();

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
