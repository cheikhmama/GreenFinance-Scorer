import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { RequireRole } from "@/shared/RequireRole";
import { CompaniesPage } from "./components/CompaniesPage";
import { CompanyDetailPage } from "./components/CompanyDetailPage";
import { ComparisonPage } from "./components/ComparisonPage";
import { ComparisonResultsPage } from "./components/ComparisonResultsPage";
import { InvestorDashboardPage } from "./components/InvestorDashboardPage";
import { PortfolioDetailPage } from "./components/PortfolioDetailPage";
import { PortfoliosPage } from "./components/PortfoliosPage";
import { ProfilePage } from "./components/ProfilePage";

export const investorRoutes: RouteObject[] = [
  {
    element: (
      <RequireRole allowedRoles={["INVESTOR"]}>
        <AppShell />
      </RequireRole>
    ),
    children: [
      { path: "/investor", element: <InvestorDashboardPage /> },
      { path: "/investor/entreprises", element: <CompaniesPage /> },
      { path: "/investor/entreprises/:entrepriseId", element: <CompanyDetailPage /> },
      { path: "/investor/comparaison", element: <ComparisonPage /> },
      { path: "/investor/comparaison/resultats", element: <ComparisonResultsPage /> },
      { path: "/investor/portefeuilles", element: <PortfoliosPage /> },
      { path: "/investor/portefeuilles/:portefeuilleId", element: <PortfolioDetailPage /> },
      { path: "/investor/profil", element: <ProfilePage /> },
    ],
  },
];
