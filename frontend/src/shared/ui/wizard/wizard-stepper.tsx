import { Check } from "lucide-react";
import { cn } from "@/shared/ui/cn";

export interface EtapeWizard {
  id: string;
  titre: string;
}

/** Étapes d'un assistant (spec §3.1) : liste verticale sur grand écran, « Étape n sur N » au
 * téléphone. Purement présentatif : l'étape courante vient de l'URL (ou de l'état local). */
export function WizardStepper({
  etapes,
  courante,
}: {
  etapes: readonly EtapeWizard[];
  courante: string;
}) {
  const index = Math.max(
    0,
    etapes.findIndex((etape) => etape.id === courante),
  );
  return (
    <nav aria-label="Étapes">
      <p className="text-sm text-muted-foreground md:hidden">
        Étape {index + 1} sur {etapes.length} —{" "}
        <span className="font-medium text-foreground">{etapes[index]?.titre}</span>
      </p>
      <ol className="hidden flex-col gap-1 md:flex">
        {etapes.map((etape, i) => (
          <li
            key={etape.id}
            aria-current={i === index ? "step" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm",
              i === index ? "bg-secondary font-medium text-foreground" : "text-muted-foreground",
            )}
          >
            <span
              aria-hidden="true"
              className={cn(
                "grid size-6 shrink-0 place-items-center rounded-full border text-xs font-semibold",
                i < index && "border-primary bg-primary text-primary-foreground",
                i === index && "border-primary text-primary",
              )}
            >
              {i < index ? <Check className="size-3.5" /> : i + 1}
            </span>
            {etape.titre}
          </li>
        ))}
      </ol>
    </nav>
  );
}
