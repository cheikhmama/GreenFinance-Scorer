import { cn } from "@/shared/ui/cn";

const TONES = [
  "bg-brand-green-light text-brand-green",
  "bg-blue-50 text-brand-blue dark:bg-blue-950/50 dark:text-blue-300",
  "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
  "bg-violet-50 text-violet-700 dark:bg-violet-950/50 dark:text-violet-300",
] as const;

function initiales(nom: string): string {
  const parties = nom.trim().split(/\s+/).filter(Boolean);
  if (parties.length === 0) return "?";
  if (parties.length === 1) return parties[0]!.slice(0, 2).toUpperCase();
  return `${parties[0]![0]}${parties[parties.length - 1]![0]}`.toUpperCase();
}

function tonePour(cle: string): (typeof TONES)[number] {
  let hash = 0;
  for (let i = 0; i < cle.length; i++) hash = (hash * 31 + cle.charCodeAt(i)) >>> 0;
  return TONES[hash % TONES.length]!;
}

/** Avatar à initiales pour une personne identifiée par son nom/e-mail (Chercheur, Institution) —
 * quand aucune photo n'existe, jamais une icône générique impersonnelle. La teinte est stable
 * par personne (dérivée du texte), pas aléatoire à chaque rendu. */
export function InitialsAvatar({
  nom,
  size = "md",
  className,
}: {
  nom: string;
  size?: "sm" | "md";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "grid shrink-0 place-items-center rounded-full font-semibold",
        size === "sm" ? "size-8 text-xs" : "size-10 text-sm",
        tonePour(nom),
        className,
      )}
      aria-hidden="true"
    >
      {initiales(nom)}
    </span>
  );
}
