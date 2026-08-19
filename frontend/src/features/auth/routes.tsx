import type { RouteObject } from "react-router-dom";
import { LoginPage } from "./components/LoginPage";

/** Route publique unique du module auth. Les tableaux de bord par rôle vivent dans
 * leurs propres modules `features/<espace>/routes.tsx` et redirigent ici (via
 * shared/RequireRole.tsx) en l'absence de session valide. */
export const authRoutes: RouteObject[] = [{ path: "/login", element: <LoginPage /> }];
