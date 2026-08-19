import type { RouteObject } from "react-router-dom";
import { RequireRole } from "@/shared/RequireRole";
import { AuditDashboardPage } from "./components/AuditDashboardPage";

export const auditRoutes: RouteObject[] = [
  {
    path: "/audit",
    element: (
      <RequireRole allowedRoles={["AUDITEUR"]}>
        <AuditDashboardPage />
      </RequireRole>
    ),
  },
];
