import { Check, Circle } from "lucide-react";
import { cn } from "@/shared/ui/cn";
import { MOT_DE_PASSE_LONGUEUR_MIN } from "../schemas";

/** Critères suivis pendant la saisie. Seule la longueur est exigée (règle du serveur, 12
 * caractères) ; les trois autres renforcent la jauge sans bloquer l'envoi. */
const CRITERES = [
  {
    libelle: `${MOT_DE_PASSE_LONGUEUR_MIN} caractères au moins`,
    exige: true,
    test: (v: string) => v.length >= MOT_DE_PASSE_LONGUEUR_MIN,
  },
  {
    libelle: "Majuscules et minuscules",
    exige: false,
    test: (v: string) => /[a-z]/.test(v) && /[A-Z]/.test(v),
  },
  { libelle: "Au moins un chiffre", exige: false, test: (v: string) => /\d/.test(v) },
  { libelle: "Au moins un symbole", exige: false, test: (v: string) => /[^A-Za-z0-9]/.test(v) },
] as const;

const NIVEAUX = [
  { libelle: "Trop court", classe: "bg-destructive" },
  { libelle: "Faible", classe: "bg-amber-500" },
  { libelle: "Moyen", classe: "bg-amber-400" },
  { libelle: "Bon", classe: "bg-emerald-500" },
  { libelle: "Fort", classe: "bg-emerald-600" },
] as const;

export function PasswordCriteria({ value, confirmation }: { value: string; confirmation: string }) {
  const resultats = CRITERES.map((critere) => critere.test(value));
  // Sous la longueur minimale, la jauge reste au plus bas quels que soient les autres critères.
  const niveau = resultats[0] ? resultats.filter(Boolean).length : 0;
  const { libelle, classe } = NIVEAUX[niveau];
  const correspondent = confirmation.length > 0 && confirmation === value;

  return (
    <div className="space-y-3 rounded-xl border bg-muted/40 p-4" aria-live="polite">
      <div className="flex items-center gap-3">
        <div className="flex flex-1 gap-1" aria-hidden="true">
          {[1, 2, 3, 4].map((barre) => (
            <span
              key={barre}
              className={cn(
                "h-1.5 flex-1 rounded-full transition-colors",
                value && barre <= Math.max(niveau, 1) ? classe : "bg-border",
              )}
            />
          ))}
        </div>
        <span className="shrink-0 whitespace-nowrap text-xs font-medium text-muted-foreground">
          {value ? `Robustesse : ${libelle.toLowerCase()}` : ""}
        </span>
      </div>
      <ul className="grid gap-1.5 text-xs sm:grid-cols-2" aria-label="Critères du mot de passe">
        {CRITERES.map((critere, index) => (
          <Critere
            key={critere.libelle}
            ok={resultats[index]}
            libelle={critere.exige ? `${critere.libelle} (requis)` : critere.libelle}
          />
        ))}
        <Critere ok={correspondent} libelle="Les deux saisies correspondent" />
      </ul>
    </div>
  );
}

function Critere({ ok, libelle }: { ok: boolean; libelle: string }) {
  return (
    <li className={cn("flex items-center gap-2", ok ? "text-foreground" : "text-muted-foreground")}>
      {ok ? (
        <Check className="size-3.5 text-primary" aria-hidden="true" />
      ) : (
        <Circle className="size-3.5" aria-hidden="true" />
      )}
      {libelle}
      <span className="sr-only">{ok ? " : rempli" : " : non rempli"}</span>
    </li>
  );
}
