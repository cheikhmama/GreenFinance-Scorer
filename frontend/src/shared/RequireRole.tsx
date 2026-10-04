import { LogOut, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useCurrentUser, useLogout } from "@/features/auth/api";
import type { Role } from "@/features/auth/schemas";
import { libelleRole } from "@/shared/format/role";
import { ROLE_HOME } from "@/shared/roleHome";
import { Badge } from "@/shared/ui/badge";
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

/** Écran d'accès restreint (403) : l'espace demandé, le compte connecté et son rôle, et les deux
 * sorties utiles — son propre espace, ou changer de compte — jamais un code de rôle brut
 * (« Votre rôle (RESEARCHER) ne permet pas… »). */
function AccesRefuse({ espaceDemande }: { espaceDemande: Role }) {
  const { data: user } = useCurrentUser();
  const logout = useLogout();
  const navigate = useNavigate();
  if (!user) return null;

  const roleConnecte = libelleRole(user.role);
  const espaceCible = libelleRole(espaceDemande);

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <section
        aria-labelledby="acces-refuse-titre"
        className="flex w-full max-w-xl flex-col gap-6 rounded-2xl border bg-card p-6 shadow-(--shadow-e2) sm:p-8"
      >
        <span className="inline-flex w-fit items-center gap-2 rounded-full border border-warning-border bg-warning-soft px-3 py-1 text-xs font-semibold text-warning">
          <ShieldAlert className="size-4" aria-hidden="true" />
          Accès restreint (403)
        </span>

        <div className="space-y-2">
          <h1 id="acces-refuse-titre" className="text-2xl font-semibold text-foreground">
            Accès non autorisé
          </h1>
          <p className="text-[15px] leading-6 text-muted-foreground">
            Votre compte actuel (<strong className="text-foreground">{roleConnecte}</strong> —{" "}
            <span className="font-medium text-foreground">{user.email}</span>) ne dispose pas des
            autorisations nécessaires pour accéder à l’espace{" "}
            <strong className="text-foreground">{espaceCible}</strong>.
          </p>
        </div>

        <dl className="grid gap-3 rounded-xl border bg-muted px-4 py-4 text-sm sm:grid-cols-[auto_1fr] sm:gap-x-6">
          <dt className="text-muted-foreground">Rôle connecté</dt>
          <dd>
            <Badge variant="info">{roleConnecte}</Badge>
          </dd>
          <dt className="text-muted-foreground">Compte</dt>
          <dd className="font-mono text-[13px] text-foreground [overflow-wrap:anywhere]">
            {user.email}
          </dd>
          <dt className="text-muted-foreground">Destination demandée</dt>
          <dd className="font-medium text-foreground">Espace {espaceCible}</dd>
        </dl>

        <div className="flex flex-col gap-2 sm:flex-row">
          <Button asChild className="sm:flex-1">
            <Link to={ROLE_HOME[user.role]}>Aller à mon espace {roleConnecte}</Link>
          </Button>
          <Button
            variant="outline"
            className="sm:flex-1"
            loading={logout.isPending}
            onClick={() =>
              logout.mutate(undefined, { onSuccess: () => navigate("/login", { replace: true }) })
            }
          >
            <LogOut aria-hidden="true" />
            Changer de compte
          </Button>
        </div>
      </section>
    </main>
  );
}
