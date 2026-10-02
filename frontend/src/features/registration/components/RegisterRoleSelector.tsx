import { ArrowLeft, Building2, ChevronRight, GraduationCap, TrendingUp } from "lucide-react";
import { Link } from "react-router-dom";
import { AuthLayout } from "@/shared/layout/AuthLayout";

const ROLES = [
  {
    to: "/inscription/entreprise",
    titre: "Entreprise (Émetteur)",
    description:
      "Soumettez vos rapports ESG, suivez votre conformité et obtenez votre score officiel.",
    Icone: Building2,
  },
  {
    to: "/inscription/investisseur",
    titre: "Investisseur / Analyste",
    description:
      "Consultez les scores ESG validés, analysez les rapports et évaluez vos portefeuilles.",
    Icone: TrendingUp,
  },
  {
    to: "/inscription/chercheur",
    titre: "Chercheur / Académique",
    description: "Accédez aux données agrégées et aux méthodologies de notation pour la recherche.",
    Icone: GraduationCap,
  },
];

/** Choix du profil avant l'inscription (tâche 5.10) : chaque carte mène à son formulaire. */
export function RegisterRoleSelector() {
  return (
    <AuthLayout eyebrow="REJOINDRE LA PLATEFORME" title="Créer un compte">
      <nav aria-label="Profil à inscrire">
        <ul className="grid gap-3">
          {ROLES.map(({ to, titre, description, Icone }) => (
            <li key={to}>
              <Link
                to={to}
                className="group flex items-center gap-4 rounded-xl border bg-card p-4 text-card-foreground transition hover:border-primary hover:bg-muted/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              >
                <span className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-secondary text-primary">
                  <Icone className="size-5" aria-hidden="true" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold text-foreground">{titre}</span>
                  <span className="mt-0.5 block text-sm text-muted-foreground">{description}</span>
                </span>
                <ChevronRight
                  className="size-5 shrink-0 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-primary"
                  aria-hidden="true"
                />
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <Link
        to="/login"
        className="mt-6 flex items-center justify-center gap-2 rounded text-sm font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-4"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Retour à la connexion
      </Link>
    </AuthLayout>
  );
}
