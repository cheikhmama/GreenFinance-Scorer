import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RegistrationStatusView } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { RegistrationStatusPage } from "./RegistrationStatusPage";

const JETON = "a".repeat(43);
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function vue(surcharges: Partial<RegistrationStatusView> = {}): RegistrationStatusView {
  return {
    company_name: "Minière du Nord",
    status: "PENDING_ONBOARDING",
    registered_at: "2026-09-30T10:00:00",
    info_request_message: null,
    info_requested_at: null,
    rejection_reason: null,
    rejected_at: null,
    can_respond: false,
    ...surcharges,
  };
}

function renderPage(url: string) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[url]}>
        <RegistrationStatusPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RegistrationStatusPage", () => {
  it("refuse un lien mal formé sans appeler l’API", () => {
    renderPage("/inscription-entreprise/suivi?token=court");

    expect(screen.getByText("Lien de suivi invalide")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("envoie le jeton dans le corps et affiche l’examen en cours", async () => {
    fetchMock.mockResolvedValue(Response.json(vue()));
    renderPage(`/inscription-entreprise/suivi?token=${JETON}`);

    expect(await screen.findByText("En cours d’examen")).toBeInTheDocument();
    expect(screen.getByText("Inscription à valider")).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/companies/registration-status");
    expect(init?.body).toBe(JSON.stringify({ token: JETON }));
  });

  it("affiche la demande d’informations et envoie la nouvelle lettre", async () => {
    fetchMock
      .mockResolvedValueOnce(
        Response.json(
          vue({
            status: "INFO_REQUESTED",
            info_request_message: "La lettre n’est pas signée.",
            info_requested_at: "2026-09-30T12:00:00",
            can_respond: true,
          }),
        ),
      )
      .mockResolvedValueOnce(Response.json(vue()));
    renderPage(`/inscription-entreprise/suivi?token=${JETON}`);
    const user = userEvent.setup();

    expect(await screen.findByText("La lettre n’est pas signée.")).toBeInTheDocument();
    await user.upload(
      screen.getByLabelText("Nouvelle lettre de mandat (PDF)"),
      new File(["%PDF-1.4"], "signee.pdf", { type: "application/pdf" }),
    );
    await user.type(screen.getByLabelText("Message (facultatif)"), "Version signée.");
    await user.click(screen.getByRole("button", { name: "Envoyer ma réponse" }));

    expect(await screen.findByText("En cours d’examen")).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/v1/companies/registration-status/reply");
    const corps = init?.body as FormData;
    expect(corps.get("token")).toBe(JETON);
    expect(corps.get("message")).toBe("Version signée.");
    expect((corps.get("mandate_letter") as File).name).toBe("signee.pdf");
  });

  it("affiche le motif d’un refus et propose une nouvelle demande", async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        vue({
          status: "REJECTED",
          rejection_reason: "Mandat non conforme.",
          rejected_at: "2026-09-30T12:00:00",
        }),
      ),
    );
    renderPage(`/inscription-entreprise/suivi?token=${JETON}`);

    expect(await screen.findByText("Mandat non conforme.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "déposer une nouvelle demande" })).toHaveAttribute(
      "href",
      "/inscription/entreprise",
    );
  });

  it("traite un jeton inconnu comme un lien invalide", async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        { error: { code: "suivi_introuvable", message: "Lien de suivi invalide ou expiré." } },
        { status: 404 },
      ),
    );
    renderPage(`/inscription-entreprise/suivi?token=${JETON}`);

    expect(await screen.findByText("Lien de suivi invalide")).toBeInTheDocument();
  });
});
