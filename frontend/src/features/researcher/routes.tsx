import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { RequireRole } from "@/shared/RequireRole";
import { ResearcherDashboardPage } from "./components/ResearcherDashboardPage";

export const researcherRoutes: RouteObject[] = [
  {
    element: (
      <RequireRole allowedRoles={["CHERCHEUR"]}>
        <AppShell />
      </RequireRole>
    ),
    children: [{ path: "/researcher", element: <ResearcherDashboardPage /> }],
  },
];
