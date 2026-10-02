import { ArrowRight, Building2, GraduationCap, TrendingUp } from "lucide-react";
import { Link } from "react-router-dom";
import { AuthLayout } from "@/shared/layout/AuthLayout";

const ROLES = [
  {
    to: "/inscription/entreprise",
    titre: "Entreprise (Émetteur)",
    description:
      "Soumettez vos déclarations ESG, suivez votre conformité et obtenez votre score officiel.",
    action: "Inscrire mon entreprise",
    Icone: Building2,
  },
  {
    to: "/inscription/investisseur",
    titre: "Investisseur / Analyste",
    description:
      "Consultez les scores certifiés, analysez les rapports ESG et évaluez vos portefeuilles.",
    action: "Demander un accès",
    Icone: TrendingUp,
  },
  {
    to: "/inscription/chercheur",
    titre: "Chercheur / Académique",
    description: "Accédez aux données agrégées et aux méthodologies de notation pour la recherche.",
    action: "Demander un accès",
    Icone: GraduationCap,
  },
];

/** Choix du profil avant l'inscription (tâche 5.10) : trois cartes côte à côte (empilées sur
 * mobile), chacune mène à son formulaire. */
export function RegisterRoleSelector() {
  return (
    <AuthLayout
      layout="centered"
      eyebrow="REJOINDRE LA PLATEFORME"
      title="Créer un compte"
      description="Choisissez votre profil : chaque espace a son propre parcours de validation."
    >
      <nav aria-label="Profil à inscrire">
        <ul className="grid gap-4 md:grid-cols-3">
          {ROLES.map(({ to, titre, description, action, Icone }) => (
            <li key={to} className="flex">
              <Link
                to={to}
                className="group relative flex w-full flex-col overflow-hidden rounded-2xl border bg-card p-5 text-left text-card-foreground transition duration-200 hover:-translate-y-0.5 hover:border-primary hover:shadow-lg focus-visible:border-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              >
                {/* Indicateur de la carte survolée ou ciblée au clavier. */}
                <span
                  aria-hidden="true"
                  className="absolute inset-x-0 top-0 h-1 origin-left scale-x-0 bg-primary transition-transform duration-200 group-hover:scale-x-100 group-focus-visible:scale-x-100"
                />
                <span className="flex size-12 items-center justify-center rounded-xl bg-secondary text-primary transition group-hover:bg-primary group-hover:text-primary-foreground">
                  <Icone className="size-6" aria-hidden="true" />
                </span>
                <span className="mt-4 block text-base font-semibold text-foreground">{titre}</span>
                <span className="mt-1.5 block flex-1 text-sm leading-6 text-muted-foreground">
                  {description}
                </span>
                <span className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-primary">
                  {action}
                  <ArrowRight
                    className="size-4 transition group-hover:translate-x-0.5"
                    aria-hidden="true"
                  />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <p className="mt-6 text-center text-sm text-muted-foreground">
        Déjà un compte ?{" "}
        <Link
          to="/login"
          className="rounded font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-4"
        >
          Se connecter
        </Link>
      </p>
    </AuthLayout>
  );
}
