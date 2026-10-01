import { Check } from "lucide-react";
import { cn } from "@/shared/ui/cn";
import { ETAPES, etapeCourante, type RapportSession } from "./etat";

/** Les étapes d'une déclaration vues par l'Entreprise (tâche 5.8) : préparation (brouillon,
 * fichier, liste de complétude), soumission, examen verrouillé, décision. */
export function SessionStepper({ rapport }: { rapport: RapportSession }) {
  const courante = etapeCourante(rapport);
  const terminee = courante === ETAPES.length - 1;

  return (
    <ol aria-label="Étapes de la déclaration" className="flex flex-wrap items-center gap-2">
      {ETAPES.map((etape, index) => {
        const franchie = index < courante || (terminee && index === courante);
        const active = index === courante;
        return (
          <li
            key={etape}
            aria-current={active ? "step" : undefined}
            className="flex items-center gap-2 text-sm"
          >
            <span
              className={cn(
                "flex size-6 items-center justify-center rounded-full border text-xs font-semibold",
                franchie && "border-primary bg-primary text-primary-foreground",
                active && !franchie && "border-brand-blue text-brand-blue",
                !franchie && !active && "text-brand-grey",
              )}
            >
              {franchie ? <Check className="size-3.5" aria-hidden="true" /> : index + 1}
            </span>
            <span className={cn(active ? "font-semibold text-brand-blue" : "text-brand-grey")}>
              {etape}
            </span>
            {index < ETAPES.length - 1 ? (
              <span aria-hidden="true" className="mx-1 h-px w-6 bg-border" />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
