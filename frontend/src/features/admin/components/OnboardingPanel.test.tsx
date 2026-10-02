import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { KycReport } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { OnboardingPanel } from "./OnboardingPanel";

const ID = "11111111-1111-1111-1111-111111111111";
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

const RAPPORT: KycReport = {
  company_id: ID,
  company_name: "Minière du Nord",
  status: "PENDING_ONBOARDING",
  country: "MR",
  tax_id: "12345678",
  tax_id_type: "NIF",
  lei: "5493001KJTIIGC8Y1R12",
  isin: null,
  website: "https://miniere.mr",
  contact_name: "Aïcha Ba",
  contact_email: "aicha@miniere.mr",
  registered_at: "2026-09-30T10:00:00",
  mandate_letter_available: true,
  mandate_letter_uploaded_at: "2026-09-30T10:00:00",
  info_request_message: null,
  info_requested_at: null,
  info_response_message: null,
  checked_at: "2026-10-01T09:00:00",
  checks: [
    {
      code: "gleif_registration",
      label: "Enregistrement LEI",
      result: "PASSED",
      detail: "Enregistrement ISSUED, entité ACTIVE.",
      source: "GLEIF — api.gleif.org",
    },
    {
      code: "gleif_legal_name",
      label: "Nom légal",
      result: "FAILED",
      detail: "Nom déclaré « Minière du Nord », nom légal GLEIF « MDN Holding ».",
      source: "GLEIF — api.gleif.org",
    },
    {
      code: "contact_domain",
      label: "Domaine du contact",
      result: "NOT_VERIFIABLE",
      detail: "GLEIF n'a pas répondu.",
      source: "E-mail du demandeur et site web déclaré",
    },
    {
      code: "mandate_letter",
      label: "Lettre de mandat",
      result: "PASSED",
      detail: "Déposée le 30/09/2026.",
      source: "Lettre de mandat déposée avec la demande",
    },
  ],
};

function repondre(decision: string, statut: string) {
  fetchMock.mockImplementation(async (url, init) =>
    String(url).endsWith("/kyc")
      ? Response.json(RAPPORT)
      : init?.method === "PATCH"
        ? Response.json({ company_id: ID, decision, status: statut, onboarded_at: null })
        : Response.json({}),
  );
}

function renderPanel() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <OnboardingPanel entrepriseId={ID} statut="PENDING_ONBOARDING" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function ouvrir() {
  const user = userEvent.setup();
  renderPanel();
  await user.click(screen.getByRole("button", { name: /Examiner la demande/ }));
  const fenetre = await screen.findByRole("dialog");
  await within(fenetre).findByText("Contrôles automatiques");
  return { user, fenetre };
}

function appelsPatch() {
  return fetchMock.mock.calls.filter(([, init]) => init?.method === "PATCH");
}

describe("Fenêtre KYC d’une inscription", () => {
  it("montre chaque contrôle avec son résultat et sa source, et la lettre de mandat", async () => {
    repondre("approve", "ACTIVE");
    const { fenetre } = await ouvrir();

    expect(within(fenetre).getByText("Nom légal")).toBeInTheDocument();
    expect(within(fenetre).getByText("Écart")).toBeInTheDocument();
    expect(within(fenetre).getByText("Non vérifiable")).toBeInTheDocument();
    expect(within(fenetre).getAllByText("Conforme")).toHaveLength(2);
    expect(within(fenetre).getAllByText(/Source : GLEIF/)).toHaveLength(2);
    expect(within(fenetre).getByRole("link", { name: /Ouvrir/ })).toHaveAttribute(
      "href",
      `/api/v1/admin/companies/${ID}/mandate-letter`,
    );
  });

  it("approuve après confirmation, sans être bloqué par un écart", async () => {
    repondre("approve", "ACTIVE");
    const { user, fenetre } = await ouvrir();

    await user.click(within(fenetre).getByRole("button", { name: /Approuver/ }));
    await user.click(within(fenetre).getByRole("button", { name: "Confirmer l’approbation" }));

    expect(await screen.findByRole("button", { name: /Examiner la demande/ })).toBeInTheDocument();
    expect(appelsPatch()).toEqual([
      [
        `/api/v1/admin/companies/${ID}/onboard`,
        expect.objectContaining({ body: JSON.stringify({ decision: "approve" }) }),
      ],
    ]);
  });

  it("exige un message pour demander des informations, puis l’envoie", async () => {
    repondre("request_info", "INFO_REQUESTED");
    const { user, fenetre } = await ouvrir();

    await user.click(within(fenetre).getByRole("button", { name: /Demander des informations/ }));
    const envoyer = within(fenetre).getByRole("button", { name: "Envoyer la demande" });
    expect(envoyer).toBeDisabled();
    await user.type(
      within(fenetre).getByLabelText(/Message au demandeur/),
      "Joignez une lettre signée.",
    );
    await user.click(envoyer);

    await vi.waitFor(() => expect(appelsPatch()).toHaveLength(1));
    expect(appelsPatch()[0][1]?.body).toBe(
      JSON.stringify({ decision: "request_info", message: "Joignez une lettre signée." }),
    );
  });

  it("exige un motif pour refuser, puis l’envoie", async () => {
    repondre("reject", "REJECTED");
    const { user, fenetre } = await ouvrir();

    await user.click(within(fenetre).getByRole("button", { name: /Refuser/ }));
    await user.type(within(fenetre).getByLabelText(/Motif du refus/), "Mandat non conforme.");
    await user.click(within(fenetre).getByRole("button", { name: "Confirmer le refus" }));

    await vi.waitFor(() => expect(appelsPatch()).toHaveLength(1));
    expect(appelsPatch()[0][1]?.body).toBe(
      JSON.stringify({ decision: "reject", reason: "Mandat non conforme." }),
    );
  });
});
