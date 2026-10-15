import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import axe from "axe-core";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "@/features/auth/components/LoginPage";
import { CompanyRegistrationPage } from "@/features/company/components/CompanyRegistrationPage";
import { ContactPage } from "@/features/contact/components/ContactPage";
import { MentionsLegalesPage } from "@/features/legal/components/MentionsLegalesPage";
import { PolitiqueConfidentialitePage } from "@/features/legal/components/PolitiqueConfidentialitePage";
import { AccessRequestPage } from "@/features/registration/components/AccessRequestPage";

/** Contrôle automatique axe-core (WCAG 2.x A et AA) des pages publiques. Il ne remplace pas une
 * passe manuelle au clavier et au lecteur d'écran, mais empêche une régression évidente (champ
 * sans libellé, image sans alternative, ARIA invalide) d'arriver en production. Le contraste n'est
 * pas mesurable sous jsdom (aucun rendu) : vérifié dans le navigateur. */
async function violations(page: ReactElement) {
  const { container } = render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>{page}</MemoryRouter>
    </QueryClientProvider>,
  );
  const resultat = await axe.run(container, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] },
    rules: { "color-contrast": { enabled: false } },
  });
  return resultat.violations.map(
    (v) => `${v.id} (${v.impact}) : ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`,
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({ detail: "non simulé" }, { status: 404 })),
  );
});
afterEach(() => vi.unstubAllGlobals());

describe("accessibilité automatique des pages publiques (axe-core)", () => {
  it.each([
    ["connexion", <LoginPage key="p" />],
    ["contact", <ContactPage key="p" />],
    ["inscription entreprise", <CompanyRegistrationPage key="p" />],
    ["demande d’accès investisseur", <AccessRequestPage key="p" profil="investisseur" />],
    ["politique de confidentialité", <PolitiqueConfidentialitePage key="p" />],
    ["mentions légales", <MentionsLegalesPage key="p" />],
  ])("%s : aucune violation", async (_nom, page) => {
    expect(await violations(page)).toEqual([]);
  });
});
