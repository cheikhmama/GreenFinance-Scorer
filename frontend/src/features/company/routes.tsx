import type { RouteObject } from "react-router-dom";
import { RequireRole } from "@/shared/RequireRole";
import { CompanyDashboardPage } from "./components/CompanyDashboardPage";

export const companyRoutes: RouteObject[] = [
  {
    path: "/company",
    element: (
      <RequireRole allowedRoles={["ENTREPRISE"]}>
        <CompanyDashboardPage />
      </RequireRole>
    ),
  },
];
