import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { RequireRole } from "@/shared/RequireRole";
import { CompanyDashboardPage } from "./components/CompanyDashboardPage";
import { CompanyDepositPage } from "./components/CompanyDepositPage";
import { CompanyReportDetailPage } from "./components/CompanyReportDetailPage";
import { CompanyReportsPage } from "./components/CompanyReportsPage";
import { ProfilePage } from "./components/ProfilePage";

export const companyRoutes: RouteObject[] = [
  {
    element: (
      <RequireRole allowedRoles={["ENTREPRISE"]}>
        <AppShell />
      </RequireRole>
    ),
    children: [
      { path: "/company", element: <CompanyDashboardPage /> },
      { path: "/company/rapports", element: <CompanyReportsPage /> },
      { path: "/company/rapports/:rapportId", element: <CompanyReportDetailPage /> },
      { path: "/company/deposer", element: <CompanyDepositPage /> },
      { path: "/company/profil", element: <ProfilePage /> },
    ],
  },
];
