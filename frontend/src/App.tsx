import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";
import { adminRoutes } from "@/features/admin/routes";
import { auditRoutes } from "@/features/audit/routes";
import { authRoutes } from "@/features/auth/routes";
import { companyRoutes } from "@/features/company/routes";
import { institutionRoutes } from "@/features/institution/routes";
import { investorRoutes } from "@/features/investor/routes";
import { researcherRoutes } from "@/features/researcher/routes";
import { DashboardRedirect } from "@/shared/DashboardRedirect";

/**
 * Assemblage des routes de chaque module `features/*`. App.tsx ne connaît que la
 * liste des modules et où les monter ; le détail de chaque espace (garde de rôle,
 * page) reste défini dans son propre `routes.tsx`, jamais ici.
 */
const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/dashboard" replace /> },
  { path: "/dashboard", element: <DashboardRedirect /> },
  ...authRoutes,
  ...adminRoutes,
  ...companyRoutes,
  ...auditRoutes,
  ...investorRoutes,
  ...researcherRoutes,
  ...institutionRoutes,
]);

export function App() {
  return <RouterProvider router={router} />;
}
