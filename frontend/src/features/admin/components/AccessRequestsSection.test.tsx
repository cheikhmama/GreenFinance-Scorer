import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConfirmProvider } from "@/shared/ui/confirm-dialog";
import { AccessRequestsSection } from "./AccessRequestsSection";

const fetchMock = vi.fn<typeof fetch>();

const DEMANDE = {
  id: "d1",
  user_id: "u1",
  role: "RESEARCHER",
  full_name: "Moussa Diop",
  email: "moussa@univ-nkc.mr",
  organization: "Université de Nouakchott",
  investor_type: null,
  research_domain: "CARBON_FOOTPRINT",
  status: "PENDING_APPROVAL",
  requested_at: "2026-10-01T09:00:00Z",
  decided_at: null,
  rejection_reason: null,
};

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (_url, init) =>
    init?.method === "PATCH"
      ? Response.json({ ...DEMANDE, status: "APPROVED" })
      : Response.json([DEMANDE]),
  );
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function renderSection() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ConfirmProvider>
        <AccessRequestsSection />
      </ConfirmProvider>
    </QueryClientProvider>,
  );
}

function patchs() {
  return fetchMock.mock.calls.filter(([, init]) => init?.method === "PATCH");
}

describe("Administration — demandes d’accès", () => {
  it("liste les demandes en attente et approuve après confirmation", async () => {
    const user = userEvent.setup();
    renderSection();

    const liste = await screen.findByRole("list", { name: "Demandes d’accès en attente" });
    expect(liste).toHaveTextContent("Moussa Diop");
    expect(liste).toHaveTextContent("Chercheur");
    expect(liste).toHaveTextContent("Université de Nouakchott · Empreinte carbone");
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/admin/access-requests?status=PENDING_APPROVAL",
    );

    await user.click(within(liste).getByRole("button", { name: /Approuver/ }));
    const dialogue = await screen.findByRole("dialog");
    await user.click(within(dialogue).getByRole("button", { name: "Approuver" }));

    await waitFor(() => expect(patchs()).toHaveLength(1));
    expect(patchs()[0]?.[0]).toBe("/api/v1/admin/access-requests/d1");
    expect(JSON.parse(patchs()[0]?.[1]?.body as string)).toEqual({ decision: "approve" });
  });

  it("refuse avec un motif obligatoire", async () => {
    const user = userEvent.setup();
    renderSection();

    await user.click(await screen.findByRole("button", { name: /Refuser/ }));
    const dialogue = await screen.findByRole("dialog");
    const valider = within(dialogue).getByRole("button", { name: "Refuser la demande" });
    expect(valider).toBeDisabled();

    await user.type(
      within(dialogue).getByLabelText("Motif du refus"),
      "Organisme non identifiable.",
    );
    await user.click(valider);

    await waitFor(() => expect(patchs()).toHaveLength(1));
    expect(JSON.parse(patchs()[0]?.[1]?.body as string)).toEqual({
      decision: "reject",
      reason: "Organisme non identifiable.",
    });
  });

  it("ne s’affiche pas sans demande en attente", async () => {
    fetchMock.mockImplementation(async () => Response.json([]));
    const { container } = renderSection();

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
