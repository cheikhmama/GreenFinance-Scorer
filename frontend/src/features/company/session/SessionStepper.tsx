import { Check, FilePen, Gavel, type LucideIcon, Send, ShieldCheck } from "lucide-react";
import { cn } from "@/shared/ui/cn";
import { ETAPES, etapeCourante, type RapportSession } from "./etat";

const ICONES: Record<(typeof ETAPES)[number], LucideIcon> = {
  Préparation: FilePen,
  Soumission: Send,
  Examen: ShieldCheck,
  Décision: Gavel,
};

/** Les étapes d'une déclaration vues par l'Entreprise (tâche 5.9) : préparation (brouillon,
 * fichier, liste de complétude), soumission, examen, décision. Une icône par étape ; franchie,
 * en cours ou à venir se lisent par la couleur ET la forme (coche, anneau, contour) — rendu
 * identique en clair et en sombre, jetons de thème uniquement. */
export function SessionStepper({ rapport }: { rapport: RapportSession }) {
  const courante = etapeCourante(rapport);
  const terminee = courante === ETAPES.length - 1;

  return (
    <ol aria-label="Étapes de la déclaration" className="flex flex-wrap items-center gap-y-2">
      {ETAPES.map((etape, index) => {
        const franchie = index < courante || (terminee && index === courante);
        const active = index === courante && !franchie;
        const Icone = franchie ? Check : ICONES[etape];
        return (
          <li
            key={etape}
            aria-current={index === courante ? "step" : undefined}
            className="flex items-center"
          >
            <span className="flex items-center gap-2">
              <span
                className={cn(
                  "flex size-7 items-center justify-center rounded-full border",
                  franchie && "border-primary bg-primary text-primary-foreground",
                  active && "border-primary bg-background text-primary ring-2 ring-primary/20",
                  !franchie && !active && "border-border bg-muted text-muted-foreground",
                )}
              >
                <Icone className="size-3.5" aria-hidden="true" />
              </span>
              <span
                className={cn(
                  "text-sm",
                  active ? "font-semibold text-foreground" : "text-muted-foreground",
                  franchie && "text-foreground",
                )}
              >
                {etape}
                <span className="sr-only">
                  {franchie ? " (terminée)" : active ? " (en cours)" : " (à venir)"}
                </span>
              </span>
            </span>
            {index < ETAPES.length - 1 ? (
              <span
                aria-hidden="true"
                className={cn(
                  "mx-3 h-px w-8 sm:w-12",
                  index < courante ? "bg-primary" : "bg-border",
                )}
              />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
