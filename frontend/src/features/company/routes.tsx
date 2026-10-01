import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { RequireRole } from "@/shared/RequireRole";
import { CompanyDashboardPage } from "./components/CompanyDashboardPage";
import { CompanyDepositPage } from "./components/CompanyDepositPage";
import { CompanyRegistrationPage } from "./components/CompanyRegistrationPage";
import { CompanyReportDetailPage } from "./components/CompanyReportDetailPage";
import { CompanyReportsPage } from "./components/CompanyReportsPage";
import { ProfilePage } from "./components/ProfilePage";
import { RegistrationStatusPage } from "./components/RegistrationStatusPage";

export const companyRoutes: RouteObject[] = [
  // Publique : inscription d'une entreprise, validée ensuite par l'Administrateur (décision D5).
  { path: "/inscription-entreprise", element: <CompanyRegistrationPage /> },
  // Publique : suivi de la demande, avec le jeton reçu par e-mail (tâche 5.2).
  { path: "/inscription-entreprise/suivi", element: <RegistrationStatusPage /> },
  {
    element: (
      <RequireRole allowedRoles={["ENTERPRISE"]}>
        <AppShell />
      </RequireRole>
    ),
    children: [
      { path: "/company", element: <CompanyDashboardPage /> },
      { path: "/company/rapports", element: <CompanyReportsPage /> },
      { path: "/company/rapports/:rapportId", element: <CompanyReportDetailPage /> },
      { path: "/company/deposer", element: <CompanyDepositPage /> },
      { path: "/company/profil", element: <ProfilePage /> },
    ],
  },
];
