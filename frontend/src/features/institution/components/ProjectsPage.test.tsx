import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectsPage } from "./ProjectsPage";

const fetchMock = vi.fn<typeof fetch>();
const PROJET = {
  id: "99999999-9999-9999-9999-999999999999",
  institution_id: "1",
  name: "Mines et climat",
  description: null,
  objective: "Comparer l’intensité carbone du secteur minier.",
  start_date: "2026-10-01",
  planned_end_date: "2027-03-31",
  deadline: null,
  status: "OUVERT",
  created_at: "2026-09-30T00:00:00",
  closed_at: null,
};

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("Espace Institution — créer un projet", () => {
  it("vérifie les dates, crée le projet et l’affiche dans la liste", async () => {
    let cree = false;
    fetchMock.mockImplementation(async (_url, init) => {
      if (init?.method === "POST") {
        cree = true;
        return Response.json(PROJET, { status: 201 });
      }
      return Response.json(cree ? [PROJET] : []);
    });
    const user = userEvent.setup();
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter>
          <ProjectsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText(/Aucun projet pour l'instant/)).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Créer un projet" })[0]);
    const dialogue = await screen.findByRole("dialog");
    await user.type(within(dialogue).getByLabelText("Nom du projet"), "Mines et climat");
    await user.type(within(dialogue).getByLabelText("Début"), "2027-04-01");
    await user.type(within(dialogue).getByLabelText("Fin prévue"), "2027-03-31");
    await user.click(within(dialogue).getByRole("button", { name: "Créer" }));

    expect(
      await within(dialogue).findByText("La date de début doit précéder la date de fin prévue."),
    ).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);

    await user.clear(within(dialogue).getByLabelText("Début"));
    await user.type(within(dialogue).getByLabelText("Début"), "2026-10-01");
    await user.click(within(dialogue).getByRole("button", { name: "Créer" }));

    // Dialogue fermé, liste relue : le nouveau projet figure dans la table ; son tiroir mène au
    // détail.
    expect(await screen.findByText("Mines et climat")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await user.click(
      await screen.findByRole("button", { name: "Voir le détail de Mines et climat" }),
    );
    const lien = await screen.findByRole("link", { name: "Ouvrir le projet" });
    expect(lien).toHaveAttribute("href", `/institution/projets/${PROJET.id}`);
    const envoi = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(envoi?.[0]).toBe("/api/v1/institution/projets");
    expect(JSON.parse(envoi?.[1]?.body as string)).toEqual({
      name: "Mines et climat",
      description: null,
      objective: null,
      start_date: "2026-10-01",
      planned_end_date: "2027-03-31",
      deadline: null,
    });
  });
});
