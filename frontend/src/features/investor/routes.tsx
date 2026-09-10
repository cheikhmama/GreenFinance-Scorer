import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { RequireRole } from "@/shared/RequireRole";
import { CompaniesPage } from "./components/CompaniesPage";
import { CompanyDetailPage } from "./components/CompanyDetailPage";
import { ComparisonPage } from "./components/ComparisonPage";
import { InvestorDashboardPage } from "./components/InvestorDashboardPage";
import { PortfolioDetailPage } from "./components/PortfolioDetailPage";
import { PortfoliosPage } from "./components/PortfoliosPage";

export const investorRoutes: RouteObject[] = [
  {
    element: (
      <RequireRole allowedRoles={["INVESTISSEUR"]}>
        <AppShell />
      </RequireRole>
    ),
    children: [
      { path: "/investor", element: <InvestorDashboardPage /> },
      { path: "/investor/entreprises", element: <CompaniesPage /> },
      { path: "/investor/entreprises/:entrepriseId", element: <CompanyDetailPage /> },
      { path: "/investor/comparaison", element: <ComparisonPage /> },
      { path: "/investor/portefeuilles", element: <PortfoliosPage /> },
      { path: "/investor/portefeuilles/:portefeuilleId", element: <PortfolioDetailPage /> },
    ],
  },
];
