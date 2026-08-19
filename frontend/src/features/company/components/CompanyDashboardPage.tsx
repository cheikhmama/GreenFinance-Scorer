import { useCurrentUser } from "@/features/auth/api";

/**
 * Tableau de bord placeholder de l'espace Entreprise. Aucune fonctionnalité
 * métier : app/company/router.py est encore un router vide côté backend (Étape 10).
 * Confirme seulement que RequireRole a laissé passer l'utilisateur.
 */
export function CompanyDashboardPage() {
  const { data: user } = useCurrentUser();

  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold text-brand-blue">Espace Entreprise</h1>
      <p className="mt-2 text-brand-grey">Connecté en tant que {user?.email}</p>
    </div>
  );
}
