import { Check } from "lucide-react";
import { cn } from "./cn";

/** Progression d'un objet en phases ordonnées (spec §5.2). Les phases franchies et la courante
 * sont pleines ; une branche (« Correction demandée »…) est dite en toutes lettres à côté. */
export function PhaseProgress({
  etapes,
  courante,
  branche = null,
  label = "Progression",
}: {
  etapes: readonly string[];
  courante: number;
  branche?: { libelle: string; ton: "attention" | "danger" } | null;
  label?: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <ol aria-label={label} className="flex flex-wrap items-center gap-2">
        {etapes.map((etape, i) => {
          const franchie = i < courante;
          const active = i === courante;
          return (
            <li
              key={etape}
              aria-current={active ? "step" : undefined}
              className="flex items-center gap-2 text-sm"
            >
              {i > 0 ? <span aria-hidden="true" className="h-px w-4 bg-border sm:w-6" /> : null}
              <span
                className={cn(
                  "grid size-6 place-items-center rounded-full border text-xs font-semibold",
                  franchie && "border-primary bg-primary text-primary-foreground",
                  active && "border-primary text-primary",
                  !franchie && !active && "text-muted-foreground",
                )}
                aria-hidden="true"
              >
                {franchie ? <Check className="size-3.5" /> : i + 1}
              </span>
              <span
                className={cn(
                  active ? "font-medium text-foreground" : "text-muted-foreground",
                  !active && "sr-only sm:not-sr-only",
                )}
              >
                {etape}
              </span>
            </li>
          );
        })}
      </ol>
      {branche ? (
        <p
          className={cn(
            "text-sm font-medium",
            branche.ton === "danger" ? "text-danger" : "text-warning",
          )}
        >
          {branche.libelle}
        </p>
      ) : null}
    </div>
  );
}
