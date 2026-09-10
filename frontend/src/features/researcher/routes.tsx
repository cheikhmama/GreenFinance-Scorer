import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { RequireRole } from "@/shared/RequireRole";
import { AnalyseDetailPage } from "./components/AnalyseDetailPage";
import { AnalysesPage } from "./components/AnalysesPage";
import { CompanyDetailPage } from "./components/CompanyDetailPage";
import { ComparisonPage } from "./components/ComparisonPage";
import { DonneesPage } from "./components/DonneesPage";
import { RattachementsPage } from "./components/RattachementsPage";
import { ResearcherDashboardPage } from "./components/ResearcherDashboardPage";

export const researcherRoutes: RouteObject[] = [
  {
    element: (
      <RequireRole allowedRoles={["CHERCHEUR"]}>
        <AppShell />
      </RequireRole>
    ),
    children: [
      { path: "/researcher", element: <ResearcherDashboardPage /> },
      { path: "/researcher/entreprises", element: <DonneesPage /> },
      { path: "/researcher/entreprises/:entrepriseId", element: <CompanyDetailPage /> },
      { path: "/researcher/comparaison", element: <ComparisonPage /> },
      { path: "/researcher/analyses", element: <AnalysesPage /> },
      { path: "/researcher/analyses/:analyseId", element: <AnalyseDetailPage /> },
      { path: "/researcher/rattachements", element: <RattachementsPage /> },
    ],
  },
];
