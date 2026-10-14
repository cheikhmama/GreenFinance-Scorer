import type { ReactNode } from "react";
import type { Params } from "react-router-dom";

/** `handle` des routes de l'application. `fil` : libellé de la route dans le fil d'Ariane (spec
 * §2.2) — une fonction quand il dépend d'un paramètre ou d'une donnée (« Déclaration FY2025 »).
 * `pleineLargeur` : la page occupe toute la largeur (tâche 5.7). */
export interface HandleRoute {
  pleineLargeur?: boolean;
  fil?: string | ((params: Readonly<Params<string>>) => ReactNode);
}
