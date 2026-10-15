import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "./dialog";
import { Sheet, SheetContent, SheetTitle } from "./sheet";

/** Fenêtres contrôlées sans Trigger, comme la plupart de celles de l'application. */
function DialogControle() {
  const [ouvert, setOuvert] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOuvert(true)}>
        Ouvrir la fenêtre
      </button>
      <Dialog open={ouvert} onOpenChange={setOuvert}>
        <DialogContent>
          <DialogTitle>Fenêtre</DialogTitle>
          <DialogDescription>contenu</DialogDescription>
        </DialogContent>
      </Dialog>
    </>
  );
}

function SheetControle() {
  const [ouvert, setOuvert] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOuvert(true)}>
        Ouvrir le tiroir
      </button>
      <Sheet open={ouvert} onOpenChange={setOuvert}>
        <SheetContent aria-describedby={undefined}>
          <SheetTitle>Tiroir</SheetTitle>
        </SheetContent>
      </Sheet>
    </>
  );
}

describe("retour du focus à la fermeture", () => {
  it("Dialog contrôlé : Échap rend le focus au bouton qui l'a ouvert", async () => {
    const user = userEvent.setup();
    render(<DialogControle />);
    const bouton = screen.getByRole("button", { name: "Ouvrir la fenêtre" });

    await user.click(bouton);
    expect(await screen.findByRole("dialog", { name: "Fenêtre" })).toBeInTheDocument();
    await user.keyboard("{Escape}");

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(bouton).toHaveFocus();
  });

  it("Sheet contrôlé : le bouton Fermer rend le focus au bouton qui l'a ouvert", async () => {
    const user = userEvent.setup();
    render(<SheetControle />);
    const bouton = screen.getByRole("button", { name: "Ouvrir le tiroir" });

    await user.click(bouton);
    await user.click(await screen.findByRole("button", { name: "Fermer" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(bouton).toHaveFocus();
  });
});
