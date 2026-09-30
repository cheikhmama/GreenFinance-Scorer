import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { RequireRole } from "@/shared/RequireRole";
import { AnalyseDetailPage } from "./components/AnalyseDetailPage";
import { AnalysesPage } from "./components/AnalysesPage";
import { CompanyDetailPage } from "./components/CompanyDetailPage";
import { ComparisonPage } from "./components/ComparisonPage";
import { CrossValidationPage } from "./components/CrossValidationPage";
import { DonneesPage } from "./components/DonneesPage";
import { ProfilePage } from "./components/ProfilePage";
import { ProjetDetailPage } from "./components/ProjetDetailPage";
import { ProjetsPage } from "./components/ProjetsPage";
import { RattachementsPage } from "./components/RattachementsPage";
import { ResearcherDashboardPage } from "./components/ResearcherDashboardPage";

export const researcherRoutes: RouteObject[] = [
  {
    element: (
      <RequireRole allowedRoles={["RESEARCHER"]}>
        <AppShell />
      </RequireRole>
    ),
    children: [
      { path: "/researcher", element: <ResearcherDashboardPage /> },
      { path: "/researcher/entreprises", element: <DonneesPage /> },
      { path: "/researcher/entreprises/:entrepriseId", element: <CompanyDetailPage /> },
      { path: "/researcher/comparaison", element: <ComparisonPage /> },
      { path: "/researcher/projets", element: <ProjetsPage /> },
      { path: "/researcher/projets/:projetId", element: <ProjetDetailPage /> },
      { path: "/researcher/analyses", element: <AnalysesPage /> },
      { path: "/researcher/analyses/:analyseId", element: <AnalyseDetailPage /> },
      { path: "/researcher/rattachements", element: <RattachementsPage /> },
      { path: "/researcher/validation-croisee", element: <CrossValidationPage /> },
      { path: "/researcher/profil", element: <ProfilePage /> },
    ],
  },
];
