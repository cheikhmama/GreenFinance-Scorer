import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { RequireRole } from "@/shared/RequireRole";
import { InvestorDashboardPage } from "./components/InvestorDashboardPage";

export const investorRoutes: RouteObject[] = [
  {
    element: (
      <RequireRole allowedRoles={["INVESTISSEUR"]}>
        <AppShell />
      </RequireRole>
    ),
    children: [{ path: "/investor", element: <InvestorDashboardPage /> }],
  },
];
