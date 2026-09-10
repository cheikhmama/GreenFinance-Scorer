import type { StatutRattachement } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

const LIBELLES: Record<StatutRattachement, string> = {
  EN_ATTENTE: "En attente",
  ACCEPTE: "Accepté",
  REFUSE: "Refusé",
};

const VARIANTES: Record<
  StatutRattachement,
  "default" | "secondary" | "destructive" | "outline" | "success" | "warning"
> = {
  EN_ATTENTE: "warning",
  ACCEPTE: "success",
  REFUSE: "destructive",
};

export function libelleStatutRattachement(statut: StatutRattachement): string {
  return LIBELLES[statut];
}

export function variantStatutRattachement(statut: StatutRattachement) {
  return VARIANTES[statut];
}
