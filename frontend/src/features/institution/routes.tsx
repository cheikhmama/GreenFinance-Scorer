import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { RequireRole } from "@/shared/RequireRole";
import { AnalyseDetailPage } from "./components/AnalyseDetailPage";
import { AnalysesPage } from "./components/AnalysesPage";
import { CompaniesPage } from "./components/CompaniesPage";
import { CompanyDetailPage } from "./components/CompanyDetailPage";
import { InstitutionDashboardPage } from "./components/InstitutionDashboardPage";
import { ProfilePage } from "./components/ProfilePage";
import { ProjectDetailPage } from "./components/ProjectDetailPage";
import { ProjectsPage } from "./components/ProjectsPage";
import { ResearchersPage } from "./components/ResearchersPage";

export const institutionRoutes: RouteObject[] = [
  {
    element: (
      <RequireRole allowedRoles={["INSTITUTION"]}>
        <AppShell />
      </RequireRole>
    ),
    children: [
      { path: "/institution", element: <InstitutionDashboardPage /> },
      { path: "/institution/entreprises", element: <CompaniesPage /> },
      { path: "/institution/entreprises/:entrepriseId", element: <CompanyDetailPage /> },
      { path: "/institution/chercheurs", element: <ResearchersPage /> },
      { path: "/institution/projets", element: <ProjectsPage /> },
      { path: "/institution/projets/:projetId", element: <ProjectDetailPage /> },
      { path: "/institution/analyses", element: <AnalysesPage /> },
      { path: "/institution/analyses/:analyseId", element: <AnalyseDetailPage /> },
      { path: "/institution/profil", element: <ProfilePage /> },
    ],
  },
];
