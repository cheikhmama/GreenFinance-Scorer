import { Navigate, type RouteObject, useParams } from "react-router-dom";
import { libellePilier } from "@/shared/format/indicateurs";
import { AppShell } from "@/shared/layout/AppShell";
import type { HandleRoute } from "@/shared/layout/handle";
import { RouteError } from "@/shared/layout/RouteError";
import { RequireRole } from "@/shared/RequireRole";
import { CompanyDashboardPage } from "./components/CompanyDashboardPage";
import { CompanyDeclarationsPage } from "./components/CompanyDeclarationsPage";
import { ProfilePage } from "./components/ProfilePage";
import { RegistrationStatusPage } from "./components/RegistrationStatusPage";
import { DeclarationLayout } from "./declaration/DeclarationLayout";
import { FilDeclaration } from "./declaration/FilDeclaration";
import { MetricSheet } from "./declaration/MetricSheet";
import { OverviewPage } from "./declaration/OverviewPage";
import { PillarPage } from "./declaration/PillarPage";
import { libelleFamille, pilierDepuisSlug } from "./esg/taxonomie";

/** Anciennes adresses d'un rapport (avant la tâche 5.9) : liens d'e-mails et favoris restent bons. */
function AncienneDeclaration() {
  const { rapportId } = useParams<{ rapportId: string }>();
  return <Navigate to={`/company/declarations/${rapportId}`} replace />;
}

/** Arbre de l'espace Entreprise (spec §2) : chaque niveau est une route imbriquée qui déclare
 * son libellé de fil d'Ariane. Exporté sans garde ni AppShell pour les tests. */
export const companyEspaceRoutes: RouteObject[] = [
  {
    path: "/company",
    handle: { fil: "Tableau de bord" } satisfies HandleRoute,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <CompanyDashboardPage /> },
      {
        path: "declarations",
        handle: { fil: "Mes déclarations" } satisfies HandleRoute,
        children: [
          { index: true, element: <CompanyDeclarationsPage /> },
          {
            path: ":rapportId",
            element: <DeclarationLayout />,
            errorElement: <RouteError />,
            handle: {
              fil: (params) => <FilDeclaration segment={params.rapportId ?? ""} />,
            } satisfies HandleRoute,
            children: [
              { element: <OverviewPage />, children: [{ index: true }] },
              {
                path: ":pilier",
                element: <PillarPage />,
                errorElement: <RouteError />,
                handle: {
                  fil: (params) => {
                    const pilier = pilierDepuisSlug(params.pilier);
                    return pilier ? libellePilier(pilier) : "Section";
                  },
                } satisfies HandleRoute,
                children: [
                  {
                    path: ":famille",
                    handle: {
                      fil: (params) => {
                        const pilier = pilierDepuisSlug(params.pilier);
                        return (pilier && libelleFamille(pilier, params.famille)) ?? "Famille";
                      },
                    } satisfies HandleRoute,
                    children: [{ path: ":code", element: <MetricSheet /> }],
                  },
                ],
              },
            ],
          },
        ],
      },
      {
        path: "profile",
        element: <ProfilePage />,
        handle: { fil: "Profil entreprise" } satisfies HandleRoute,
      },
      // Adresses d'avant la tâche 5.9.
      { path: "rapports", element: <Navigate to="/company/declarations" replace /> },
      { path: "rapports/:rapportId", element: <AncienneDeclaration /> },
      { path: "deposer", element: <Navigate to="/company/declarations" replace /> },
      { path: "profil", element: <Navigate to="/company/profile" replace /> },
    ],
  },
];

export const companyRoutes: RouteObject[] = [
  // L'inscription elle-même vit dans features/registration (tâche 5.10).
  // Publique : suivi de la demande, avec le jeton reçu par e-mail (tâche 5.2).
  { path: "/inscription-entreprise/suivi", element: <RegistrationStatusPage /> },
  {
    element: (
      <RequireRole allowedRoles={["ENTERPRISE"]}>
        <AppShell />
      </RequireRole>
    ),
    children: companyEspaceRoutes,
  },
];
