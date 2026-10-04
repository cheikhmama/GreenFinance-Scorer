import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/shared/ui/button";

/** Retour à la liste d'une page de détail — même forme que « Mes déclarations » (espace
 * Entreprise) : les pages de détail des autres espaces n'avaient aucun chemin de retour. */
export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Button asChild variant="ghost" size="sm" className="-ml-2 text-muted-foreground">
      <Link to={to}>
        <ArrowLeft aria-hidden="true" />
        {children}
      </Link>
    </Button>
  );
}
