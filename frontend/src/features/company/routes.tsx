import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { RequireRole } from "@/shared/RequireRole";
import { CompanyDashboardPage } from "./components/CompanyDashboardPage";
import { CompanyReportDetailPage } from "./components/CompanyReportDetailPage";

export const companyRoutes: RouteObject[] = [
  {
    element: (
      <RequireRole allowedRoles={["ENTREPRISE"]}>
        <AppShell />
      </RequireRole>
    ),
    children: [
      { path: "/company", element: <CompanyDashboardPage /> },
      { path: "/company/rapports/:rapportId", element: <CompanyReportDetailPage /> },
    ],
  },
];
