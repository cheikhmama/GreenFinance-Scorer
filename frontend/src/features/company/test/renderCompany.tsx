import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router-dom";
import { Breadcrumbs } from "@/shared/layout/Breadcrumbs";
import { ConfirmProvider } from "@/shared/ui/confirm-dialog";
import { companyEspaceRoutes } from "../routes";

/** Monte l'arbre de routes de l'espace Entreprise (sans garde de rôle ni AppShell, qui
 * demanderaient /auth/me) avec le fil d'Ariane, dans un routeur de données en mémoire. */
export function renderCompany(chemin: string) {
  const router = createMemoryRouter(
    [
      {
        element: (
          <>
            <Breadcrumbs />
            <Outlet />
          </>
        ),
        children: companyEspaceRoutes,
      },
    ],
    { initialEntries: [chemin] },
  );
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ConfirmProvider>
        <RouterProvider router={router} />
      </ConfirmProvider>
    </QueryClientProvider>,
  );
  return { router, queryClient };
}
