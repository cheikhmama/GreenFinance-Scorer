import { User } from "lucide-react";

const PALETTE = [
  "bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300",
  "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300",
  "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300",
  "bg-violet-100 text-violet-700 dark:bg-violet-950/60 dark:text-violet-300",
  "bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300",
  "bg-cyan-100 text-cyan-700 dark:bg-cyan-950/60 dark:text-cyan-300",
];

function initiales(nom: string): string {
  const mots = nom.trim().split(/\s+/).filter(Boolean);
  if (mots.length === 0) return "?";
  if (mots.length === 1) return mots[0].slice(0, 2).toUpperCase();
  return (mots[0].charAt(0) + mots[1].charAt(0)).toUpperCase();
}

function couleurDeterministe(nom: string): string {
  const hash = nom.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return PALETTE[hash % PALETTE.length] ?? PALETTE[0];
}

/** Photo de profil si renseignée, sinon un repli par défaut — même principe que
 * shared/esg/CompanyAvatar.tsx, décliné en cercle pour une personne plutôt qu'un rectangle
 * arrondi pour une entreprise (langage visuel cohérent, formes distinctes).
 *
 * `fallback` choisit ce repli : "initiales" (défaut, des initiales déterministes colorées —
 * utilisé dans ProfileIdentityCard, où l'utilisateur voit son propre avatar en grand) ou
 * "icone" (une icône de profil générique — utilisé dans AppShell, sur le rail sombre fixe de
 * la sidebar). Le style "icone" (blanc translucide) est calibré pour ce fond marine fixe, pas
 * pour un fond clair : à ajuster si un jour réutilisé ailleurs. */
export function UserAvatar({
  nom,
  avatar,
  className = "size-10",
  fallback = "initiales",
}: {
  nom: string;
  avatar: string | null;
  className?: string;
  fallback?: "initiales" | "icone";
}) {
  if (avatar) {
    return <img src={avatar} alt={nom} className={`${className} rounded-full object-cover`} />;
  }
  if (fallback === "icone") {
    return (
      <div
        className={`${className} grid place-items-center rounded-full bg-white/15 text-white`}
        aria-hidden="true"
      >
        <User className="size-[55%]" />
      </div>
    );
  }
  return (
    <div
      className={`${className} grid place-items-center rounded-full font-bold ${couleurDeterministe(nom)}`}
      aria-hidden="true"
    >
      {initiales(nom)}
    </div>
  );
}
