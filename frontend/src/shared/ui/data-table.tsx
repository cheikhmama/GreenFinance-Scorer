import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Columns3,
  Download,
  Rows3,
  Rows4,
  Search,
} from "lucide-react";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Button } from "@/shared/ui/button";
import { cn } from "@/shared/ui/cn";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/ui/popover";
import { Skeleton } from "@/shared/ui/skeleton";

/* Table de données de l'Administration (tâche 5.17) : colonnes d'identification seulement, le
   détail et les actions vivent dans le tiroir ouvert par la ligne. Recherche instantanée, filtres
   à choix multiples (avec recherche dans les options), tri par colonne, colonnes masquables,
   export CSV / JSON des lignes filtrées et triées, densité, pagination 10 à 100 et un seul
   compteur, en pied de table. */

export type Alignement = "gauche" | "centre" | "droite";

export interface ColonneTable<T> {
  id: string;
  entete: string;
  cellule: (ligne: T) => ReactNode;
  alignement?: Alignement;
  /** Présente : la colonne est triable. `null` est toujours classé en dernier. */
  valeurTri?: (ligne: T) => string | number | null;
  /** Valeur exportée ; par défaut la valeur de tri. */
  valeurExport?: (ligne: T) => string | number | null;
  /** Faux : toujours visible (première colonne). */
  masquable?: boolean;
  classeCellule?: string;
}

export interface FiltreTable<T> {
  id: string;
  libelle: string;
  valeur: (ligne: T) => string | null;
  libelleOption?: (valeur: string) => string;
}

export interface DataTableProps<T> {
  /** Légende lue par les lecteurs d'écran (« Entreprises »). */
  libelle: string;
  lignes: T[] | undefined;
  colonnes: ColonneTable<T>[];
  cle: (ligne: T) => string;
  rechercheDans: (ligne: T) => string;
  placeholderRecherche?: string;
  filtres?: FiltreTable<T>[];
  /** Ouvre le détail de la ligne (tiroir) ; ajoute la colonne « Actions ». */
  surOuvrir?: (ligne: T) => void;
  libelleLigne?: (ligne: T) => string;
  ligneActive?: string | null;
  triInitial?: { colonne: string; sens: "asc" | "desc" };
  chargement?: boolean;
  erreur?: boolean;
  messageVide?: string;
  nomExport?: string;
  /** Contrôles propres à l'écran, placés après les filtres. */
  barre?: ReactNode;
  /** Clé de mémorisation (densité, colonnes) par table, dans ce navigateur. */
  memoire?: string;
  /** Valeurs de filtre présélectionnées (ex. le rôle venu de l'URL), par id de filtre. */
  filtresInitiaux?: Record<string, string[]>;
}

const TAILLES = [10, 25, 50, 100];

function plier(texte: string): string {
  return texte.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function lire<V>(cle: string | undefined, defaut: V): V {
  if (!cle) return defaut;
  try {
    const brut = localStorage.getItem(`table:${cle}`);
    return brut ? { ...defaut, ...JSON.parse(brut) } : defaut;
  } catch {
    return defaut;
  }
}

function ecrire(cle: string | undefined, valeur: unknown) {
  if (!cle) return;
  try {
    localStorage.setItem(`table:${cle}`, JSON.stringify(valeur));
  } catch {
    // Stockage indisponible (navigation privée) : réglage non retenu, sans conséquence.
  }
}

function classeAlignement(alignement: Alignement | undefined) {
  return alignement === "droite" ? "text-right" : alignement === "centre" ? "text-center" : "text-left";
}

function telecharger(nom: string, type: string, contenu: string) {
  const url = URL.createObjectURL(new Blob([contenu], { type }));
  const lien = document.createElement("a");
  lien.href = url;
  lien.download = nom;
  lien.click();
  URL.revokeObjectURL(url);
}

function FiltreMultiple<T>({
  filtre,
  lignes,
  choisis,
  surChanger,
}: {
  filtre: FiltreTable<T>;
  lignes: T[];
  choisis: string[];
  surChanger: (valeurs: string[]) => void;
}) {
  const [recherche, setRecherche] = useState("");
  const options = useMemo(() => {
    const valeurs = new Set<string>();
    for (const ligne of lignes) {
      const v = filtre.valeur(ligne);
      if (v) valeurs.add(v);
    }
    return [...valeurs]
      .map((v) => ({ valeur: v, libelle: filtre.libelleOption?.(v) ?? v }))
      .sort((a, b) => a.libelle.localeCompare(b.libelle, "fr"));
  }, [lignes, filtre]);
  const visibles = options.filter((o) => plier(o.libelle).includes(plier(recherche)));
  const actif = choisis.length > 0;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={cn(actif && "border-info bg-info-soft text-info hover:bg-info-soft")}
        >
          {filtre.libelle}
          {actif ? (
            <span className="rounded-full bg-info px-1.5 font-mono text-[11px] text-white dark:text-background">
              {choisis.length}
            </span>
          ) : null}
          <ChevronDown className="size-3.5" aria-hidden="true" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 p-1.5">
        {options.length > 6 ? (
          <label className="mb-1 flex items-center gap-2 border-b px-2 pb-1.5">
            <Search className="size-3.5 text-muted-foreground" aria-hidden="true" />
            <span className="sr-only">Rechercher dans {filtre.libelle}</span>
            <input
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              placeholder="Rechercher…"
              className="h-8 w-full bg-transparent text-sm outline-none"
            />
          </label>
        ) : null}
        <fieldset className="flex max-h-64 flex-col overflow-y-auto">
          <legend className="sr-only">{filtre.libelle}</legend>
          {visibles.map((o) => (
            <label
              key={o.valeur}
              className="flex min-h-9 cursor-pointer items-center gap-2.5 rounded-md px-2 text-sm hover:bg-muted"
            >
              <input
                type="checkbox"
                className="size-4 accent-(--primary)"
                checked={choisis.includes(o.valeur)}
                onChange={() =>
                  surChanger(
                    choisis.includes(o.valeur)
                      ? choisis.filter((v) => v !== o.valeur)
                      : [...choisis, o.valeur],
                  )
                }
              />
              {o.libelle}
            </label>
          ))}
          {visibles.length === 0 ? (
            <p className="px-2 py-2 text-sm text-muted-foreground">Aucune option.</p>
          ) : null}
        </fieldset>
      </PopoverContent>
    </Popover>
  );
}

export function DataTable<T>({
  libelle,
  lignes,
  colonnes,
  cle,
  rechercheDans,
  placeholderRecherche = "Rechercher…",
  filtres = [],
  surOuvrir,
  libelleLigne,
  ligneActive,
  triInitial,
  chargement,
  erreur,
  messageVide = "Aucune donnée.",
  nomExport,
  barre,
  memoire,
  filtresInitiaux,
}: DataTableProps<T>) {
  const [recherche, setRecherche] = useState("");
  const [choix, setChoix] = useState<Record<string, string[]>>(filtresInitiaux ?? {});
  // Présélection changée par la navigation (ex. /admin/investisseurs puis /admin/chercheurs).
  const clePresel = JSON.stringify(filtresInitiaux ?? {});
  useEffect(() => {
    setChoix(JSON.parse(clePresel));
    setPage(1);
  }, [clePresel]);
  const [tri, setTri] = useState(triInitial ?? null);
  const [page, setPage] = useState(1);
  const [reglages, setReglages] = useState(() =>
    lire(memoire, { compact: false, parPage: 10, masquees: [] as string[] }),
  );
  useEffect(() => ecrire(memoire, reglages), [memoire, reglages]);

  const toutes = lignes ?? [];
  const filtrees = useMemo(() => {
    const q = plier(recherche.trim());
    return toutes.filter(
      (ligne) =>
        (!q || plier(rechercheDans(ligne)).includes(q)) &&
        filtres.every((f) => {
          const valeurs = choix[f.id] ?? [];
          return valeurs.length === 0 || valeurs.includes(f.valeur(ligne) ?? "");
        }),
    );
  }, [toutes, recherche, choix, filtres, rechercheDans]);

  const triees = useMemo(() => {
    const colonne = tri ? colonnes.find((c) => c.id === tri.colonne) : undefined;
    if (!tri || !colonne?.valeurTri) return filtrees;
    const valeur = colonne.valeurTri;
    return [...filtrees].sort((a, b) => {
      const va = valeur(a);
      const vb = valeur(b);
      if (va === null && vb === null) return 0;
      if (va === null) return 1;
      if (vb === null) return -1;
      const c =
        typeof va === "number" && typeof vb === "number"
          ? va - vb
          : String(va).localeCompare(String(vb), "fr", { sensitivity: "base" });
      return tri.sens === "asc" ? c : -c;
    });
  }, [filtrees, tri, colonnes]);

  const total = triees.length;
  const nbPages = Math.max(1, Math.ceil(total / reglages.parPage));
  const pageCourante = Math.min(page, nbPages);
  const debut = (pageCourante - 1) * reglages.parPage;
  const visibles = triees.slice(debut, debut + reglages.parPage);
  const colonnesVisibles = colonnes.filter((c) => !reglages.masquees.includes(c.id));
  const filtresActifs =
    recherche.trim().length > 0 || Object.values(choix).some((valeurs) => valeurs.length > 0);
  const compteur =
    nbPages > 1
      ? `Affichage ${debut + 1}–${debut + visibles.length} sur ${total}`
      : `${total} ${total > 1 ? "résultats" : "résultat"}`;
  const padding = reglages.compact ? "py-1.5" : "py-2.5";

  function trier(id: string) {
    setTri((t) => ({ colonne: id, sens: t?.colonne === id && t.sens === "asc" ? "desc" : "asc" }));
    setPage(1);
  }

  function exporter(format: "csv" | "json") {
    const valeur = (c: ColonneTable<T>, ligne: T) =>
      (c.valeurExport ?? c.valeurTri)?.(ligne) ?? null;
    const nom = `${nomExport ?? "export"}-${new Date().toISOString().slice(0, 10)}`;
    if (format === "json") {
      const objets = triees.map((ligne) =>
        Object.fromEntries(colonnes.map((c) => [c.entete, valeur(c, ligne)])),
      );
      telecharger(`${nom}.json`, "application/json", JSON.stringify(objets, null, 2));
      return;
    }
    // « ; » et BOM UTF-8 : le fichier s'ouvre directement dans Excel en français, accents compris.
    const cellule = (v: string | number | null) => {
      const texte = v === null ? "" : String(v);
      return /[;"\n]/.test(texte) ? `"${texte.replaceAll('"', '""')}"` : texte;
    };
    const csv = [
      colonnes.map((c) => cellule(c.entete)).join(";"),
      ...triees.map((ligne) => colonnes.map((c) => cellule(valeur(c, ligne))).join(";")),
    ].join("\r\n");
    telecharger(`${nom}.csv`, "text/csv;charset=utf-8", `﻿${csv}`);
  }

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <div role="search" className="flex flex-wrap items-center gap-2">
        <label className="flex h-9 max-w-xs flex-[1_1_15rem] items-center gap-2 rounded-lg border border-input bg-card px-2.5 text-muted-foreground focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/25">
          <Search className="size-4 shrink-0" aria-hidden="true" />
          <span className="sr-only">Rechercher</span>
          <input
            type="search"
            value={recherche}
            onChange={(e) => {
              setRecherche(e.target.value);
              setPage(1);
            }}
            placeholder={placeholderRecherche}
            className="h-full w-full min-w-0 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
          />
        </label>
        {filtres.map((f) => (
          <FiltreMultiple
            key={f.id}
            filtre={f}
            lignes={toutes}
            choisis={choix[f.id] ?? []}
            surChanger={(valeurs) => {
              setChoix((c) => ({ ...c, [f.id]: valeurs }));
              setPage(1);
            }}
          />
        ))}
        {barre}
        {filtresActifs ? (
          <Button
            variant="link"
            size="sm"
            onClick={() => {
              setRecherche("");
              setChoix({});
              setPage(1);
            }}
          >
            Réinitialiser
          </Button>
        ) : null}
        <div className="ml-auto flex items-center gap-2">
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm">
                <Columns3 aria-hidden="true" />
                Colonnes
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-56 p-1.5">
              <fieldset className="flex flex-col">
                <legend className="sr-only">Colonnes visibles</legend>
                {colonnes
                  .filter((c) => c.masquable !== false)
                  .map((c) => (
                    <label
                      key={c.id}
                      className="flex min-h-9 cursor-pointer items-center gap-2.5 rounded-md px-2 text-sm hover:bg-muted"
                    >
                      <input
                        type="checkbox"
                        className="size-4 accent-(--primary)"
                        checked={!reglages.masquees.includes(c.id)}
                        onChange={() =>
                          setReglages((r) => ({
                            ...r,
                            masquees: r.masquees.includes(c.id)
                              ? r.masquees.filter((id) => id !== c.id)
                              : [...r.masquees, c.id],
                          }))
                        }
                      />
                      {c.entete}
                    </label>
                  ))}
              </fieldset>
            </PopoverContent>
          </Popover>
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" disabled={total === 0}>
                <Download aria-hidden="true" />
                Exporter
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-60 p-1.5">
              <button
                type="button"
                onClick={() => exporter("csv")}
                className="flex min-h-9 w-full items-center rounded-md px-2 text-left text-sm hover:bg-muted"
              >
                CSV (Excel) · {total} lignes
              </button>
              <button
                type="button"
                onClick={() => exporter("json")}
                className="flex min-h-9 w-full items-center rounded-md px-2 text-left text-sm hover:bg-muted"
              >
                JSON
              </button>
            </PopoverContent>
          </Popover>
          <fieldset className="inline-flex overflow-hidden rounded-lg border border-input">
            <legend className="sr-only">Densité</legend>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Densité normale"
              aria-pressed={!reglages.compact}
              className={cn(
                "rounded-none",
                !reglages.compact && "bg-foreground text-background hover:bg-foreground",
              )}
              onClick={() => setReglages((r) => ({ ...r, compact: false }))}
            >
              <Rows3 aria-hidden="true" />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Densité compacte"
              aria-pressed={reglages.compact}
              className={cn(
                "rounded-none border-l border-input",
                reglages.compact && "bg-foreground text-background hover:bg-foreground",
              )}
              onClick={() => setReglages((r) => ({ ...r, compact: true }))}
            >
              <Rows4 aria-hidden="true" />
            </Button>
          </fieldset>
        </div>
      </div>

      <div className="relative min-w-0 overflow-hidden rounded-xl border bg-card shadow-(--shadow-e1)">
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[40rem] border-collapse text-[13px]">
            <caption className="sr-only">
              {libelle}
              {surOuvrir ? " — activez une ligne pour ouvrir son détail." : ""}
            </caption>
            <thead>
              <tr className="border-b bg-muted/60">
                {colonnesVisibles.map((c) => {
                  const actif = tri?.colonne === c.id;
                  return (
                    <th
                      key={c.id}
                      scope="col"
                      aria-sort={
                        actif ? (tri?.sens === "asc" ? "ascending" : "descending") : undefined
                      }
                      className={cn("px-3 text-xs font-semibold whitespace-nowrap", classeAlignement(c.alignement))}
                    >
                      {c.valeurTri ? (
                        <button
                          type="button"
                          onClick={() => trier(c.id)}
                          className="inline-flex h-9 items-center gap-1 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          {c.entete}
                          <span
                            aria-hidden="true"
                            className={cn("text-[10px]", actif ? "text-primary" : "text-input")}
                          >
                            {actif ? (tri?.sens === "asc" ? "▲" : "▼") : "↕"}
                          </span>
                        </button>
                      ) : (
                        <span className="inline-flex h-9 items-center">{c.entete}</span>
                      )}
                    </th>
                  );
                })}
                {surOuvrir ? (
                  <th scope="col" className="w-16 px-3 text-center text-xs font-semibold">
                    Actions
                  </th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {chargement
                ? Array.from({ length: 5 }, (_, i) => (
                    // biome-ignore lint/suspicious/noArrayIndexKey: lignes fantômes fixes
                    <tr key={i} className="border-t border-border/60">
                      {colonnesVisibles.map((c) => (
                        <td key={c.id} className="px-3 py-3">
                          <Skeleton className="h-3.5 w-3/4" />
                        </td>
                      ))}
                      {surOuvrir ? <td /> : null}
                    </tr>
                  ))
                : visibles.map((ligne) => {
                    const id = cle(ligne);
                    return (
                      <tr
                        key={id}
                        onClick={surOuvrir ? () => surOuvrir(ligne) : undefined}
                        className={cn(
                          "border-t border-border/60 transition-colors",
                          surOuvrir && "cursor-pointer hover:bg-muted/50",
                          ligneActive === id && "bg-secondary hover:bg-secondary",
                        )}
                      >
                        {colonnesVisibles.map((c) => (
                          <td
                            key={c.id}
                            className={cn("px-3", padding, classeAlignement(c.alignement), c.classeCellule)}
                          >
                            {c.cellule(ligne)}
                          </td>
                        ))}
                        {surOuvrir ? (
                          <td className={cn("px-3 text-center", padding)}>
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-haspopup="dialog"
                              aria-label={`Voir le détail de ${libelleLigne?.(ligne) ?? "la ligne"}`}
                              className="text-primary"
                              onClick={(e) => {
                                e.stopPropagation();
                                surOuvrir(ligne);
                              }}
                            >
                              <ChevronRight aria-hidden="true" />
                            </Button>
                          </td>
                        ) : null}
                      </tr>
                    );
                  })}
            </tbody>
          </table>
          {!chargement && erreur ? (
            <p role="alert" className="px-4 py-8 text-center text-sm text-danger">
              Impossible de charger les données. Réessayez dans un instant.
            </p>
          ) : null}
          {!chargement && !erreur && total === 0 ? (
            <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
              <p className="text-sm font-medium text-foreground">
                {filtresActifs ? "Aucun résultat pour ces critères." : messageVide}
              </p>
              {filtresActifs ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setRecherche("");
                    setChoix({});
                  }}
                >
                  Réinitialiser les filtres
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-3 border-t px-3 py-2 text-[13px] text-muted-foreground">
          <span aria-live="polite" className="font-mono text-foreground">
            {chargement ? "Chargement…" : compteur}
          </span>
          <label className="ml-auto inline-flex items-center gap-2">
            Par page
            <select
              value={reglages.parPage}
              onChange={(e) => {
                setReglages((r) => ({ ...r, parPage: Number(e.target.value) }));
                setPage(1);
              }}
              className="h-8 rounded-md border border-input bg-card px-1.5 font-mono text-[13px] text-foreground"
            >
              {TAILLES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <nav aria-label="Pagination" className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon-sm"
              aria-label="Page précédente"
              disabled={pageCourante <= 1}
              onClick={() => setPage(pageCourante - 1)}
            >
              <ChevronLeft aria-hidden="true" />
            </Button>
            <span className="px-1.5 font-mono text-foreground">
              {pageCourante} / {nbPages}
            </span>
            <Button
              variant="outline"
              size="icon-sm"
              aria-label="Page suivante"
              disabled={pageCourante >= nbPages}
              onClick={() => setPage(pageCourante + 1)}
            >
              <ChevronRight aria-hidden="true" />
            </Button>
          </nav>
        </div>
      </div>
    </div>
  );
}
