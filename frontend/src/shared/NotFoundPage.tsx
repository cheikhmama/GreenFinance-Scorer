import { Compass } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/shared/ui/button";

/** Adresse inconnue : sans cette route, React Router affichait sa page d'erreur brute (en anglais,
 * « 404 Not Found »). Le tableau de bord renvoie chacun vers son propre espace. */
export function NotFoundPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-4 text-center">
      <Compass className="size-10 text-brand-grey" aria-hidden="true" />
      <h1 className="text-2xl font-semibold text-brand-blue">Page introuvable</h1>
      <p className="max-w-md text-sm text-brand-grey">
        Cette adresse ne correspond à aucune page. Le lien est peut-être incomplet ou la page a été
        déplacée.
      </p>
      <Button asChild>
        <Link to="/dashboard">Retour à l’accueil</Link>
      </Button>
    </main>
  );
}
