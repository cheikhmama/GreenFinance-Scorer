import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { PrototypeProvider, usePrototype } from "../PrototypeContext";
import { UserProvisioningModal } from "./UserProvisioningModal";

function StateCounters() {
  const { companies, reports, users } = usePrototype();

  return (
    <div>
      <output data-testid="user-count">{users.length}</output>
      <output data-testid="company-count">{companies.length}</output>
      <output data-testid="report-count">{reports.length}</output>
    </div>
  );
}

function renderModal() {
  const onClose = vi.fn();

  render(
    <MemoryRouter>
      <PrototypeProvider>
        <StateCounters />
        <UserProvisioningModal open onClose={onClose} />
      </PrototypeProvider>
    </MemoryRouter>,
  );

  return { onClose };
}

async function selectCompanyRole(user: ReturnType<typeof userEvent.setup>) {
  await user.selectOptions(screen.getByLabelText("Rôle de l’utilisateur"), "ENTREPRISE");
}

describe("UserProvisioningModal", () => {
  it("affiche initialement uniquement le choix du rôle", () => {
    renderModal();

    expect(screen.getByRole("dialog", { name: "Ajouter un utilisateur" })).toBeInTheDocument();
    expect(screen.getByLabelText("Rôle de l’utilisateur")).toBeInTheDocument();
    expect(screen.queryByLabelText("Nom légal de l’entreprise")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Nom complet/)).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Administrateur" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Sélectionner un rôle…",
      "Entreprise",
      "Investisseur",
      "Auditeur",
      "Institution",
      "Chercheur",
    ]);
    expect(screen.getByRole("button", { name: "Ajouter un utilisateur" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Ajouter l’entreprise et inviter" }),
    ).not.toBeInTheDocument();
  });

  it("affiche automatiquement le formulaire Entreprise après le choix du rôle", async () => {
    const user = userEvent.setup();
    renderModal();

    await selectCompanyRole(user);

    expect(screen.getByLabelText(/Nom légal de l’entreprise/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Site officiel/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Secteur d’activité/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Pays/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Nom complet/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Adresse e-mail professionnelle/)).not.toBeInTheDocument();
    expect(screen.queryByTestId("company-logo")).not.toBeInTheDocument();
    expect(screen.queryByText("Logo officiel")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("URL du logo")).not.toBeInTheDocument();
    expect(screen.getByLabelText("URL officielle du rapport")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Ajouter l’entreprise et inviter" }),
    ).toBeInTheDocument();
  });

  it("simule la détection du secteur et du pays depuis microsoft.com", async () => {
    const user = userEvent.setup();
    renderModal();
    await selectCompanyRole(user);

    await user.type(screen.getByLabelText(/Site officiel/), "microsoft.com");
    await user.tab();

    expect(screen.getByRole("button", { name: "Analyse…" })).toBeDisabled();
    expect(screen.getByText("Recherche des informations publiques…")).toBeInTheDocument();

    await waitFor(
      () => {
        expect(screen.getByLabelText(/Nom légal de l’entreprise/)).toHaveValue("Microsoft");
        expect(screen.getByLabelText(/Secteur d’activité/)).toHaveValue("Technologies");
        expect(screen.getByLabelText(/Pays/)).toHaveValue("États-Unis");
      },
      { timeout: 2_000 },
    );

    expect(screen.getByText("Logo, secteur et pays renseignés automatiquement.")).toHaveClass(
      "sr-only",
    );
    expect(screen.queryByText("Confiance 96 %")).not.toBeInTheDocument();
    expect(screen.queryByTestId("company-logo")).not.toBeInTheDocument();

    fireEvent.load(screen.getByTestId("company-logo-loader"));
    expect(screen.getByTestId("company-logo")).toBeInTheDocument();
    expect(screen.queryByText("Logo officiel")).not.toBeInTheDocument();
  });

  it("renseigne Apple et n’affiche jamais l’adresse technique du logo", async () => {
    const user = userEvent.setup();
    renderModal();
    await selectCompanyRole(user);

    await user.type(screen.getByLabelText(/Site officiel/), "https://www.apple.com");
    await user.tab();

    await waitFor(
      () => {
        expect(screen.getByLabelText(/Nom légal de l’entreprise/)).toHaveValue("Apple");
        expect(screen.getByLabelText(/Secteur d’activité/)).toHaveValue("Technologies");
        expect(screen.getByLabelText(/Pays/)).toHaveValue("États-Unis");
      },
      { timeout: 2_000 },
    );

    const loader = screen.getByTestId("company-logo-loader");
    expect(loader).toHaveAttribute(
      "src",
      "https://www.apple.com/ac/structured-data/images/open_graph_logo.png",
    );
    expect(
      screen.queryByText(/open_graph_logo|apple-touch-icon|favicon\.ico/),
    ).not.toBeInTheDocument();

    fireEvent.load(loader);
    expect(screen.getByTestId("company-logo")).toBeInTheDocument();
    expect(screen.getByAltText("Logo officiel de Apple")).toBeInTheDocument();
  });

  it("détecte la SNIM et utilise une ressource graphique officielle avec repli", async () => {
    const user = userEvent.setup();
    renderModal();
    await selectCompanyRole(user);

    await user.type(screen.getByLabelText(/Site officiel/), "https://snim.com/");
    await user.tab();

    await waitFor(
      () => {
        expect(screen.getByLabelText(/Nom légal de l’entreprise/)).toHaveValue("SNIM");
        expect(screen.getByLabelText(/Secteur d’activité/)).toHaveValue("Industrie minière");
        expect(screen.getByLabelText(/Pays/)).toHaveValue("Mauritanie");
      },
      { timeout: 2_000 },
    );

    const firstCandidate = screen.getByTestId("company-logo-loader");
    expect(firstCandidate).toHaveAttribute(
      "src",
      "https://upload.wikimedia.org/wikipedia/commons/0/01/Snim_logo.svg",
    );
    expect(screen.queryByTestId("company-logo")).not.toBeInTheDocument();

    fireEvent.error(firstCandidate);
    expect(screen.getByTestId("company-logo-loader")).toHaveAttribute(
      "src",
      "https://snim.com/sites/default/files/logo_snim_final_0.jpg",
    );

    fireEvent.load(screen.getByTestId("company-logo-loader"));
    expect(screen.getByTestId("company-logo")).toBeInTheDocument();
    expect(screen.getByAltText("Logo officiel de SNIM")).toBeInTheDocument();
  });

  it("détecte Ingka Group depuis son domaine officiel", async () => {
    const user = userEvent.setup();
    renderModal();
    await selectCompanyRole(user);

    await user.type(screen.getByLabelText(/Site officiel/), "https://www.ingka.com");
    await user.tab();

    await waitFor(
      () => {
        expect(screen.getByLabelText(/Nom légal de l’entreprise/)).toHaveValue("Ingka Group");
        expect(screen.getByLabelText(/Secteur d’activité/)).toHaveValue("Commerce de détail");
        expect(screen.getByLabelText(/Pays/)).toHaveValue("Pays-Bas");
      },
      { timeout: 2_000 },
    );

    const loader = screen.getByTestId("company-logo-loader");
    expect(loader).toHaveAttribute(
      "src",
      "https://assets.site.ingka.com/ingka-old/wp-content/uploads/2018/09/Ingka.com_Navicon.png",
    );

    fireEvent.load(loader);
    expect(screen.getByTestId("company-logo")).toBeInTheDocument();
    expect(screen.getByAltText("Logo officiel de Ingka Group")).toBeInTheDocument();
  });

  it("affiche uniquement les champs propres au rôle sélectionné", async () => {
    const user = userEvent.setup();
    renderModal();
    const roleSelect = screen.getByLabelText("Rôle de l’utilisateur");

    await user.selectOptions(roleSelect, "INVESTISSEUR");
    expect(screen.getByLabelText("Type d’investisseur")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Organisation ou entreprise d’appartenance (facultatif)"),
    ).not.toBeRequired();
    expect(
      screen.getByLabelText("Préférences ou domaines d’investissement (facultatif)"),
    ).toBeInTheDocument();

    await user.selectOptions(roleSelect, "AUDITEUR");
    expect(screen.getByLabelText("Cabinet ou organisation d’appartenance *")).toBeRequired();
    expect(screen.getByLabelText("Fonction ou poste")).toBeInTheDocument();
    expect(screen.getByLabelText("Références professionnelles")).toBeInTheDocument();
    expect(screen.queryByLabelText("Type d’investisseur")).not.toBeInTheDocument();

    await user.selectOptions(roleSelect, "INSTITUTION");
    expect(screen.getByLabelText("Nom de l’institution *")).toBeRequired();
    expect(screen.getByLabelText("Pays *")).toBeRequired();
    expect(screen.getByLabelText("Site officiel *")).toBeRequired();

    await user.selectOptions(roleSelect, "CHERCHEUR");
    expect(screen.getByLabelText("Institution d’appartenance")).not.toBeRequired();
    expect(screen.getByLabelText("Domaine de recherche")).toBeInTheDocument();
    expect(screen.queryByLabelText("Site officiel *")).not.toBeInTheDocument();
  });

  it("crée le compte, l’entreprise et son premier rapport à partir d’une URL", async () => {
    const user = userEvent.setup();
    renderModal();

    expect(screen.getByTestId("user-count")).toHaveTextContent("7");
    expect(screen.getByTestId("company-count")).toHaveTextContent("3");
    expect(screen.getByTestId("report-count")).toHaveTextContent("3");

    await selectCompanyRole(user);
    await user.type(screen.getByLabelText(/Nom légal de l’entreprise/), "Solaria Labs");
    await user.type(screen.getByLabelText(/Site officiel/), "https://solaria.example");
    await user.type(screen.getByLabelText(/Secteur d’activité/), "Énergie solaire");
    await user.type(screen.getByLabelText(/Pays/), "France");
    await user.type(
      screen.getByLabelText("URL officielle du rapport"),
      "https://solaria.example/reports/esg-2025.pdf",
    );
    await user.click(screen.getByRole("button", { name: "Ajouter l’entreprise et inviter" }));

    expect(await screen.findByText("Solaria Labs est prêt")).toBeInTheDocument();
    expect(screen.getByText("Ajout terminé")).toBeInTheDocument();
    expect(screen.getByTestId("user-count")).toHaveTextContent("8");
    expect(screen.getByTestId("company-count")).toHaveTextContent("4");
    expect(screen.getByTestId("report-count")).toHaveTextContent("4");
  });
});
