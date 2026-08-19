import type { RouteObject } from "react-router-dom";
import { RequireRole } from "@/shared/RequireRole";
import { InstitutionDashboardPage } from "./components/InstitutionDashboardPage";

export const institutionRoutes: RouteObject[] = [
  {
    path: "/institution",
    element: (
      <RequireRole allowedRoles={["INSTITUTION"]}>
        <InstitutionDashboardPage />
      </RequireRole>
    ),
  },
];
