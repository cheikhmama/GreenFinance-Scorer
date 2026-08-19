import { Navigate } from "react-router-dom";
import { useCurrentUser } from "@/features/auth/api";
import type { Role } from "@/features/auth/schemas";

/** Un seul espace par rôle (voir Utilisateur.role, table à discriminant unique —
 * app/auth/models.py côté backend) : la correspondance est donc directe, sans liste. */
const ROLE_HOME: Record<Role, string> = {
  ADMINISTRATEUR: "/admin",
  ENTREPRISE: "/company",
  AUDITEUR: "/audit",
  INVESTISSEUR: "/investor",
  CHERCHEUR: "/researcher",
  INSTITUTION: "/institution",
};

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
