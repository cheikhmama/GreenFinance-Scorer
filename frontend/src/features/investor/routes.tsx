import type { RouteObject } from "react-router-dom";
import { RequireRole } from "@/shared/RequireRole";
import { InvestorDashboardPage } from "./components/InvestorDashboardPage";

export const investorRoutes: RouteObject[] = [
  {
    path: "/investor",
    element: (
      <RequireRole allowedRoles={["INVESTISSEUR"]}>
        <InvestorDashboardPage />
      </RequireRole>
    ),
  },
];
