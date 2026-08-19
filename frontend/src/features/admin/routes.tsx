import type { RouteObject } from "react-router-dom";
import { RequireRole } from "@/shared/RequireRole";
import { AdminDashboardPage } from "./components/AdminDashboardPage";

export const adminRoutes: RouteObject[] = [
  {
    path: "/admin",
    element: (
      <RequireRole allowedRoles={["ADMINISTRATEUR"]}>
        <AdminDashboardPage />
      </RequireRole>
    ),
  },
];
