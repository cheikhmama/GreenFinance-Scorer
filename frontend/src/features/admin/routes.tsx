import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { RequireRole } from "@/shared/RequireRole";
import { AdminCompaniesPage } from "./components/AdminCompaniesPage";
import { AdminCompanyReportsPage } from "./components/AdminCompanyReportsPage";
import { AdminDashboardPage } from "./components/AdminDashboardPage";
import { AdminJournalAuditPage } from "./components/AdminJournalAuditPage";
import { AdminReportDetailPage } from "./components/AdminReportDetailPage";
import { AdminReportsPage } from "./components/AdminReportsPage";
import { AdminUsersPage } from "./components/AdminUsersPage";

export const adminRoutes: RouteObject[] = [
  {
    element: (
      <RequireRole allowedRoles={["ADMINISTRATEUR"]}>
        <AppShell />
      </RequireRole>
    ),
    children: [
      { path: "/admin", element: <AdminDashboardPage /> },
      { path: "/admin/utilisateurs", element: <AdminUsersPage /> },
      { path: "/admin/entreprises", element: <AdminCompaniesPage /> },
      { path: "/admin/entreprises/:entrepriseId/rapports", element: <AdminCompanyReportsPage /> },
      { path: "/admin/rapports", element: <AdminReportsPage /> },
      { path: "/admin/rapports/:rapportId", element: <AdminReportDetailPage /> },
      { path: "/admin/journal-audit", element: <AdminJournalAuditPage /> },
    ],
  },
];
