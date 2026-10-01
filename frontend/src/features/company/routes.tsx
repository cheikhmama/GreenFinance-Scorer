import { Navigate, type RouteObject, useParams } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { RequireRole } from "@/shared/RequireRole";
import { CompanyDashboardPage } from "./components/CompanyDashboardPage";
import { CompanyDeclarationsPage } from "./components/CompanyDeclarationsPage";
import { CompanyRegistrationPage } from "./components/CompanyRegistrationPage";
import { CompanyReportDetailPage } from "./components/CompanyReportDetailPage";
import { ProfilePage } from "./components/ProfilePage";
import { RegistrationStatusPage } from "./components/RegistrationStatusPage";

/** Anciennes adresses d'un rapport (avant la tâche 5.9) : liens d'e-mails et favoris restent bons. */
function AncienneDeclaration() {
  const { rapportId } = useParams<{ rapportId: string }>();
  return <Navigate to={`/company/declarations/${rapportId}`} replace />;
}

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
      { path: "/company/declarations", element: <CompanyDeclarationsPage /> },
      { path: "/company/declarations/:rapportId", element: <CompanyReportDetailPage /> },
      { path: "/company/profile", element: <ProfilePage /> },
      // Adresses d'avant la tâche 5.9.
      { path: "/company/rapports", element: <Navigate to="/company/declarations" replace /> },
      { path: "/company/rapports/:rapportId", element: <AncienneDeclaration /> },
      { path: "/company/deposer", element: <Navigate to="/company/declarations" replace /> },
      { path: "/company/profil", element: <Navigate to="/company/profile" replace /> },
    ],
  },
];
