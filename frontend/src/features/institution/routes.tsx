import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { RequireRole } from "@/shared/RequireRole";
import { InstitutionDashboardPage } from "./components/InstitutionDashboardPage";

export const institutionRoutes: RouteObject[] = [
  {
    element: (
      <RequireRole allowedRoles={["INSTITUTION"]}>
        <AppShell />
      </RequireRole>
    ),
    children: [{ path: "/institution", element: <InstitutionDashboardPage /> }],
  },
];
