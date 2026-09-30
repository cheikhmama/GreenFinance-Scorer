import type { RouteObject } from "react-router-dom";
import { ConfirmEmailChangePage } from "./components/ConfirmEmailChangePage";
import { ForgotPasswordPage } from "./components/ForgotPasswordPage";
import { LoginPage } from "./components/LoginPage";
import { ActivateAccountPage, ResetPasswordPage } from "./components/ResetPasswordPage";

/** Routes publiques du module auth. Les tableaux de bord par rôle vivent dans leurs
 * propres modules `features/<espace>/routes.tsx` et redirigent ici (via
 * shared/RequireRole.tsx) en l'absence de session valide. Un changement de mot de passe
 * se fait toujours depuis le Profil (shared/profile/ChangePasswordDialog.tsx) — un compte
 * provisionné par l'Administrateur n'a plus de mot de passe temporaire à changer, il reçoit
 * un lien d'activation par e-mail (app/auth/activation.py) et n'ouvre sa première session
 * qu'une fois son propre mot de passe posé. */
export const authRoutes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  { path: "/mot-de-passe-oublie", element: <ForgotPasswordPage /> },
  { path: "/reinitialiser-mot-de-passe", element: <ResetPasswordPage /> },
  // Cibles des liens envoyés par app/auth/activation.py et app/auth/email_change.py.
  { path: "/activer-compte", element: <ActivateAccountPage /> },
  { path: "/confirmer-email", element: <ConfirmEmailChangePage /> },
];
