import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Fusionne des classes Tailwind conditionnelles en résolvant les conflits d'utilitaires
 * (ex. `p-2` puis `p-4` -> seul `p-4` est conservé). Requis par tous les composants
 * shadcn/ui de ce dossier (voir components.json : "utils": "@/shared/ui/cn").
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
