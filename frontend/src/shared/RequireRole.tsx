import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useCurrentUser } from "@/features/auth/api";
import type { Role } from "@/features/auth/schemas";

interface RequireRoleProps {
  allowedRoles: Role[];
  children: ReactNode;
}

/**
 * Garde de route par rôle, posée devant chaque espace utilisateur (Admin,
 * Entreprise, Auditeur, Investisseur, Chercheur, Institution — voir
 * features/<espace>/routes.tsx). S'appuie sur GET /auth/me : le cookie de session
 * étant httpOnly, c'est le seul moyen de savoir côté client si l'utilisateur est
 * authentifié.
 *
 * Un rôle non autorisé affiche un message plutôt qu'une redirection silencieuse —
 * une Entreprise qui suit un lien vers l'espace Auditeur doit comprendre pourquoi
 * l'accès lui est refusé, pas atterrir sans explication ailleurs dans l'app.
 */
export function RequireRole({ allowedRoles, children }: RequireRoleProps) {
  const { data: user, isLoading, isError } = useCurrentUser();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-brand-grey">
        Chargement...
      </div>
    );
  }

  if (isError || !user) {
    return <Navigate to="/login" replace />;
  }

  if (!allowedRoles.includes(user.role)) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 px-4 text-center">
        <p className="text-lg font-semibold text-brand-blue">Accès non autorisé</p>
        <p className="text-brand-grey">
          Votre rôle ({user.role}) ne permet pas d'accéder à cet espace.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
