import { Navigate } from "react-router-dom";
import { useCurrentUser } from "@/features/auth/api";
import { ROLE_HOME } from "@/shared/roleHome";

/**
 * Cible générique de redirection après connexion (features/auth/components/LoginPage.tsx
 * redirige vers /dashboard, pas directement vers l'espace métier). Le module auth n'a
 * pas à connaître la table de correspondance rôle -> route de chaque espace ; c'est
 * cette route qui la centralise, pour éviter de la dupliquer partout où l'app doit
 * renvoyer un utilisateur déjà connecté vers "son" espace.
 */
export function DashboardRedirect() {
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

  return <Navigate to={ROLE_HOME[user.role]} replace />;
}
