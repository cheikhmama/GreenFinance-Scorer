import type { RouteObject } from "react-router-dom";
import { RequireRole } from "@/shared/RequireRole";
import { ResearcherDashboardPage } from "./components/ResearcherDashboardPage";

export const researcherRoutes: RouteObject[] = [
  {
    path: "/researcher",
    element: (
      <RequireRole allowedRoles={["CHERCHEUR"]}>
        <ResearcherDashboardPage />
      </RequireRole>
    ),
  },
];
