import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { RequireRole } from "@/shared/RequireRole";
import { AuditDashboardPage } from "./components/AuditDashboardPage";
import { AuditHistoryPage } from "./components/AuditHistoryPage";
import { AuditReportDetailPage } from "./components/AuditReportDetailPage";

export const auditRoutes: RouteObject[] = [
  {
    element: (
      <RequireRole allowedRoles={["AUDITEUR"]}>
        <AppShell />
      </RequireRole>
    ),
    children: [
      { path: "/audit", element: <AuditDashboardPage /> },
      { path: "/audit/historique", element: <AuditHistoryPage /> },
      { path: "/audit/rapports/:rapportId", element: <AuditReportDetailPage /> },
    ],
  },
];
