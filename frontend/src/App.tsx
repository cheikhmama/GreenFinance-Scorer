import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";
import { adminRoutes } from "@/features/admin/routes";
import { auditRoutes } from "@/features/audit/routes";
import { authRoutes } from "@/features/auth/routes";
import { companyRoutes } from "@/features/company/routes";
import { contactRoutes } from "@/features/contact/routes";
import { institutionRoutes } from "@/features/institution/routes";
import { investorRoutes } from "@/features/investor/routes";
import { prototypeRoutes } from "@/features/prototype/routes";
import { registrationRoutes } from "@/features/registration/routes";
import { researcherRoutes } from "@/features/researcher/routes";
import { DashboardRedirect } from "@/shared/DashboardRedirect";
import { NotFoundPage } from "@/shared/NotFoundPage";

/**
 * Assemblage des routes de chaque module `features/*`. App.tsx ne connaît que la
 * liste des modules et où les monter ; le détail de chaque espace (garde de rôle,
 * page) reste défini dans son propre `routes.tsx`, jamais ici.
 */
const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/dashboard" replace /> },
  { path: "/dashboard", element: <DashboardRedirect /> },
  ...authRoutes,
  ...contactRoutes,
  ...registrationRoutes,
  ...adminRoutes,
  ...companyRoutes,
  ...auditRoutes,
  ...investorRoutes,
  ...researcherRoutes,
  ...institutionRoutes,
  ...prototypeRoutes,
  { path: "*", element: <NotFoundPage /> },
]);

export function App() {
  return <RouterProvider router={router} />;
}
