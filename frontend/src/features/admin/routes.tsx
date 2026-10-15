import { Navigate, type RouteObject } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { RequireRole } from "@/shared/RequireRole";
import { AdminAnalysesPage } from "./components/AdminAnalysesPage";
import { AdminAuditeursPage } from "./components/AdminAuditeursPage";
import { AdminCompaniesPage } from "./components/AdminCompaniesPage";
import { AdminCompanyDetailPage } from "./components/AdminCompanyDetailPage";
import { AdminCompanyReportsPage } from "./components/AdminCompanyReportsPage";
import { AdminDashboardPage } from "./components/AdminDashboardPage";
import { AdminJournalAuditPage } from "./components/AdminJournalAuditPage";
import { AdminPortefeuillesPage } from "./components/AdminPortefeuillesPage";
import { AdminProjetsPage } from "./components/AdminProjetsPage";
import { AdminReportDetailPage } from "./components/AdminReportDetailPage";
import { AdminReportsPage } from "./components/AdminReportsPage";
import { AdminUsersPage } from "./components/AdminUsersPage";
import { ProfilePage } from "./components/ProfilePage";

export const adminRoutes: RouteObject[] = [
  {
    element: (
      <RequireRole allowedRoles={["ADMIN"]}>
        <AppShell />
      </RequireRole>
    ),
    children: [
      { path: "/admin", element: <AdminDashboardPage /> },
      { path: "/admin/utilisateurs", element: <AdminUsersPage /> },
      // Raccourcis (tâche 5.17) : la table Utilisateurs filtrée sur le rôle, la table Rapports.
      {
        path: "/admin/investisseurs",
        element: <Navigate to="/admin/utilisateurs?role=INVESTOR" replace />,
      },
      {
        path: "/admin/chercheurs",
        element: <Navigate to="/admin/utilisateurs?role=RESEARCHER" replace />,
      },
      {
        path: "/admin/evaluations",
        element: <Navigate to="/admin/rapports?onglet=tous" replace />,
      },
      { path: "/admin/entreprises", element: <AdminCompaniesPage /> },
      { path: "/admin/entreprises/:entrepriseId", element: <AdminCompanyDetailPage /> },
      { path: "/admin/entreprises/:entrepriseId/rapports", element: <AdminCompanyReportsPage /> },
      { path: "/admin/rapports", element: <AdminReportsPage /> },
      { path: "/admin/rapports/:rapportId", element: <AdminReportDetailPage /> },
      { path: "/admin/auditeurs", element: <AdminAuditeursPage /> },
      { path: "/admin/portefeuilles", element: <AdminPortefeuillesPage /> },
      { path: "/admin/analyses", element: <AdminAnalysesPage /> },
      { path: "/admin/projets", element: <AdminProjetsPage /> },
      { path: "/admin/journal-audit", element: <AdminJournalAuditPage /> },
      { path: "/admin/profil", element: <ProfilePage /> },
    ],
  },
];
