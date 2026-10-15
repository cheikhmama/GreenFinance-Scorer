import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NotificationBell } from "./NotificationBell";

const marquerLue = vi.fn();

vi.mock("@/shared/notifications/api", () => ({
  useUnreadNotificationsCount: () => ({ data: 1 }),
  useMyNotifications: () => ({
    data: [
      {
        id: "n1",
        type: "REPORT_SUBMITTED",
        resource_id: "r1",
        message: "Nouveau rapport déposé",
        read: false,
        sent_at: "2026-10-15T08:00:00Z",
      },
      {
        id: "n2",
        type: "REPORT_SUBMITTED",
        resource_id: "r2",
        message: "Rapport déjà vu",
        read: true,
        sent_at: "2026-10-14T08:00:00Z",
      },
    ],
  }),
  useMarkNotificationRead: () => ({ mutate: marquerLue }),
  resolveNotificationLink: (_type: string, id: string) => `/rapports/${id}`,
}));

function renderCloche() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<NotificationBell />} />
        <Route path="/rapports/:id" element={<p>Page du rapport</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("NotificationBell", () => {
  beforeEach(() => marquerLue.mockClear());

  it("s’ouvre au clavier, le focus entre dans la liste, Tab la parcourt, Entrée ouvre", async () => {
    const user = userEvent.setup();
    renderCloche();
    const cloche = screen.getByRole("button", { name: "Notifications (1 non lues)" });
    expect(cloche).toHaveAttribute("aria-expanded", "false");

    cloche.focus();
    await user.keyboard("{Enter}");
    expect(cloche).toHaveAttribute("aria-expanded", "true");

    const premiere = screen.getByRole("button", { name: /Nouveau rapport déposé/ });
    await waitFor(() => expect(premiere).toHaveFocus());
    await user.tab();
    expect(screen.getByRole("button", { name: /Rapport déjà vu/ })).toHaveFocus();
    await user.tab({ shift: true });
    await user.keyboard("{Enter}");

    expect(marquerLue).toHaveBeenCalledWith("n1");
    expect(await screen.findByText("Page du rapport")).toBeInTheDocument();
  });

  it("annonce l’état non lu en texte, pas seulement par la couleur", async () => {
    const user = userEvent.setup();
    renderCloche();
    await user.click(screen.getByRole("button", { name: /Notifications/ }));

    expect(screen.getByRole("button", { name: /Nouveau rapport déposé/ })).toHaveTextContent(
      "Non lue",
    );
    expect(screen.getByRole("button", { name: /Rapport déjà vu/ })).not.toHaveTextContent(
      "Non lue",
    );
  });

  it("Échap referme le panneau et rend le focus à la cloche", async () => {
    const user = userEvent.setup();
    renderCloche();
    const cloche = screen.getByRole("button", { name: /Notifications/ });
    await user.click(cloche);
    await user.tab();

    await user.keyboard("{Escape}");

    await waitFor(() => expect(cloche).toHaveAttribute("aria-expanded", "false"));
    expect(cloche).toHaveFocus();
  });
});
