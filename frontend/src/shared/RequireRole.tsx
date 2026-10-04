import { LockKeyhole } from "lucide-react";
import type { ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useCurrentUser, useLogout } from "@/features/auth/api";
import type { Role } from "@/features/auth/schemas";
import { libelleRole } from "@/shared/format/role";
import { Button } from "@/shared/ui/button";

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
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-brand-grey">
        Chargement...
      </div>
    );
  }

  if (isError || !user) {
    // Page d'origine retenue : après reconnexion, l'utilisateur y revient (LoginPage).
    return (
      <Navigate to="/login" replace state={{ depuis: `${location.pathname}${location.search}` }} />
    );
  }

  if (!allowedRoles.includes(user.role)) {
    return <AccesRefuse espaceDemande={allowedRoles[0]} />;
  }

  return <>{children}</>;
}

/** Page d'un autre espace : dire laquelle, avec quel compte on est connecté, et proposer les deux
 * sorties utiles — son propre espace, ou changer de compte — plutôt qu'un code de rôle brut
 * (« Votre rôle (RESEARCHER) ne permet pas… »). */
function AccesRefuse({ espaceDemande }: { espaceDemande: Role }) {
  const { data: user } = useCurrentUser();
  const logout = useLogout();
  const navigate = useNavigate();
  if (!user) return null;

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="flex w-full max-w-md flex-col items-center gap-4 rounded-2xl border bg-card p-8 text-center shadow-(--shadow-e2)">
        <span className="grid size-12 place-items-center rounded-full bg-warning-soft text-warning">
          <LockKeyhole className="size-6" aria-hidden="true" />
        </span>
        <div className="space-y-2">
          <h1 className="text-xl font-semibold text-foreground">
            Cette page n’est pas pour ce compte
          </h1>
          <p className="text-[15px] leading-6 text-muted-foreground">
            Elle fait partie de l’espace {libelleRole(espaceDemande)}. Vous êtes connecté avec le
            compte {libelleRole(user.role)}{" "}
            <span className="font-medium text-foreground">{user.email}</span>.
          </p>
        </div>
        <div className="flex w-full flex-col gap-2 sm:flex-row sm:justify-center">
          <Button asChild>
            <Link to="/dashboard">Aller à mon espace</Link>
          </Button>
          <Button
            variant="outline"
            loading={logout.isPending}
            onClick={() =>
              logout.mutate(undefined, { onSuccess: () => navigate("/login", { replace: true }) })
            }
          >
            Changer de compte
          </Button>
        </div>
      </div>
    </main>
  );
}
