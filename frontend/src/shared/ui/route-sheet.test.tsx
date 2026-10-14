import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { RouteSheet } from "./route-sheet";
import { SheetBody } from "./sheet";

function Liste() {
  const { pathname } = useLocation();
  return (
    <>
      <p data-testid="chemin">{pathname}</p>
      <Link to="detail">Ouvrir le détail</Link>
      <Outlet />
    </>
  );
}

function renderSheet(chemin = "/liste") {
  return render(
    <MemoryRouter initialEntries={[chemin]}>
      <Routes>
        <Route path="/liste" element={<Liste />}>
          <Route
            path="detail"
            element={
              <RouteSheet retour="/liste" titre="Détail" taille="large">
                <SheetBody>contenu</SheetBody>
              </RouteSheet>
            }
          />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("RouteSheet", () => {
  it("s’ouvre sur sa route et revient à la route parente avec Échap", async () => {
    const user = userEvent.setup();
    renderSheet();
    const lien = screen.getByRole("link", { name: "Ouvrir le détail" });
    await user.click(lien);
    expect(await screen.findByRole("dialog", { name: "Détail" })).toHaveTextContent("contenu");

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByTestId("chemin")).toHaveTextContent("/liste");
    expect(lien).toHaveFocus();
  });

  it("s’ouvre directement depuis un lien profond", async () => {
    renderSheet("/liste/detail");
    expect(await screen.findByRole("dialog", { name: "Détail" })).toBeInTheDocument();
  });

  it("taille large : 640 px au lieu de 460 px", async () => {
    renderSheet("/liste/detail");
    const dialogue = await screen.findByRole("dialog");
    expect(dialogue.className).toContain("sm:max-w-[640px]");
    expect(dialogue.className).not.toContain("sm:max-w-[460px]");
  });
});
