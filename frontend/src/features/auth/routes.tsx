import type { RouteObject } from "react-router-dom";
import { ChangePasswordPage } from "./components/ChangePasswordPage";
import { LoginPage } from "./components/LoginPage";

/** Routes publiques du module auth. Les tableaux de bord par rôle vivent dans leurs
 * propres modules `features/<espace>/routes.tsx` et redirigent ici (via
 * shared/RequireRole.tsx) en l'absence de session valide, ou vers
 * /changer-mot-de-passe tant que doit_changer_mot_de_passe est vrai. */
export const authRoutes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  { path: "/changer-mot-de-passe", element: <ChangePasswordPage /> },
];
