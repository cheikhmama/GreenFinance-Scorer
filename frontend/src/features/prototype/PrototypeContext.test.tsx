import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { PrototypeProvider, usePrototype } from "./PrototypeContext";

function PrototypeStateHarness() {
  const {
    affiliations,
    companies,
    createUser,
    reports,
    resetDemo,
    updateAffiliation,
    updateReport,
    users,
  } = usePrototype();

  const novaReport = reports.find((report) => report.id === "rep-nova-2025");
  const novaCompany = companies.find((company) => company.id === "cmp-nova");
  const researcherAffiliation = affiliations.find((affiliation) => affiliation.id === "aff-1");
  const createdUser = users.find((user) => user.email === "fatou@prototype.test");

  return (
    <div>
      <output data-testid="user-count">{users.length}</output>
      <output data-testid="created-user">
        {createdUser ? `${createdUser.name}:${createdUser.status}` : "ABSENT"}
      </output>
      <button
        type="button"
        onClick={() =>
          createUser({
            name: "Fatou Ahmed",
            email: "fatou@prototype.test",
            role: "INVESTISSEUR",
            organization: "Impact Démo",
          })
        }
      >
        Créer Fatou
      </button>

      <output data-testid="nova-report-status">{novaReport?.status ?? "ABSENT"}</output>
      <output data-testid="nova-publication">
        {novaCompany?.published ? "PUBLIEE" : "NON_PUBLIEE"}
      </output>
      <button
        type="button"
        onClick={() =>
          updateReport("rep-nova-2025", { status: "PUBLIE" }, "Publication simulée pour le test.")
        }
      >
        Publier Nova
      </button>

      <output data-testid="affiliation-status">{researcherAffiliation?.status ?? "ABSENT"}</output>
      <button type="button" onClick={() => updateAffiliation("aff-1", "ACTIF")}>
        Activer le rattachement
      </button>
      <button type="button" onClick={resetDemo}>
        Réinitialiser
      </button>
    </div>
  );
}

function renderHarness() {
  return render(
    <PrototypeProvider>
      <PrototypeStateHarness />
    </PrototypeProvider>,
  );
}

describe("PrototypeProvider", () => {
  it("ajoute un utilisateur invité dans l’état partagé", async () => {
    const user = userEvent.setup();
    renderHarness();

    expect(screen.getByTestId("user-count")).toHaveTextContent("7");
    expect(screen.getByTestId("created-user")).toHaveTextContent("ABSENT");

    await user.click(screen.getByRole("button", { name: "Créer Fatou" }));

    expect(screen.getByTestId("user-count")).toHaveTextContent("8");
    expect(screen.getByTestId("created-user")).toHaveTextContent("Fatou Ahmed:INVITE");
  });

  it("publie un rapport et rend simultanément l’entreprise visible", async () => {
    const user = userEvent.setup();
    renderHarness();

    expect(screen.getByTestId("nova-report-status")).toHaveTextContent("A_AFFECTER");
    expect(screen.getByTestId("nova-publication")).toHaveTextContent("NON_PUBLIEE");

    await user.click(screen.getByRole("button", { name: "Publier Nova" }));

    expect(screen.getByTestId("nova-report-status")).toHaveTextContent("PUBLIE");
    expect(screen.getByTestId("nova-publication")).toHaveTextContent("PUBLIEE");
  });

  it("synchronise un rattachement puis restaure les données initiales", async () => {
    const user = userEvent.setup();
    renderHarness();

    expect(screen.getByTestId("affiliation-status")).toHaveTextContent("INVITE");

    await user.click(screen.getByRole("button", { name: "Activer le rattachement" }));
    expect(screen.getByTestId("affiliation-status")).toHaveTextContent("ACTIF");

    await user.click(screen.getByRole("button", { name: "Réinitialiser" }));
    expect(screen.getByTestId("affiliation-status")).toHaveTextContent("INVITE");
  });
});
