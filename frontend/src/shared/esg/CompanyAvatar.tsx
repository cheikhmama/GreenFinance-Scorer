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

/** Logo réel de l'entreprise si renseigné, sinon un avatar à initiales déterministe par nom —
 * jamais une image inventée pour une entreprise qui n'a pas de logo (voir la discussion sur les
 * logos synthétiques : un avatar à initiales ne prétend représenter personne). Partagé entre
 * toutes les listes/tableaux/sélections où une entreprise apparaît (voir FRONTEND-ARCHITECTURE.md
 * §2.2) : nom et logo doivent toujours être présentés ensemble. */
export function CompanyAvatar({
  nom,
  logo,
  className = "size-10",
}: {
  nom: string;
  logo: string | null;
  className?: string;
}) {
  if (logo) {
    return <img src={logo} alt={`Logo ${nom}`} className={`${className} rounded-lg object-contain`} />;
  }
  return (
    <div
      className={`${className} grid place-items-center rounded-lg text-sm font-bold ${couleurDeterministe(nom)}`}
      aria-hidden="true"
    >
      {initiales(nom)}
    </div>
  );
}

/** Nom + logo côte à côte — la présentation standard d'une entreprise partout où elle apparaît
 * (listes, tableaux, sélections, détails d'investissement). */
export function CompanyIdentity({
  nom,
  logo,
  secteur,
  avatarClassName = "size-8",
}: {
  nom: string;
  logo: string | null;
  secteur?: string;
  avatarClassName?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <CompanyAvatar nom={nom} logo={logo} className={avatarClassName} />
      <div className="min-w-0">
        <p className="truncate font-medium text-brand-blue">{nom}</p>
        {secteur ? <p className="truncate text-xs text-brand-grey">{secteur}</p> : null}
      </div>
    </div>
  );
}
