import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { RequireRole } from "@/shared/RequireRole";
import { AuditDashboardPage } from "./components/AuditDashboardPage";
import { AuditHistoryPage } from "./components/AuditHistoryPage";
import { ProfilePage } from "./components/ProfilePage";
import { AuditReviewPage } from "./review/AuditReviewPage";

export const auditRoutes: RouteObject[] = [
  {
    element: (
      <RequireRole allowedRoles={["AUDITOR"]}>
        <AppShell />
      </RequireRole>
    ),
    children: [
      { path: "/audit", element: <AuditDashboardPage /> },
      { path: "/audit/historique", element: <AuditHistoryPage /> },
      {
        path: "/audit/rapports/:rapportId",
        element: <AuditReviewPage />,
        // Espace de revue en trois volets : il occupe toute la largeur (tâche 5.7).
        handle: { pleineLargeur: true },
      },
      { path: "/audit/profil", element: <ProfilePage /> },
    ],
  },
];
