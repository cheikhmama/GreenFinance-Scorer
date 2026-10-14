import type { LucideIcon } from "lucide-react";
import { Badge } from "./badge";
import { cn } from "./cn";

export type TonStatut = "neutre" | "info" | "attention" | "succes" | "danger";

const VARIANTES = {
  neutre: "secondary",
  info: "info",
  attention: "warning",
  succes: "success",
  danger: "destructive",
} as const;

/** Statut d'objet : libellé + icône + ton (spec §5.2) — la couleur ne porte jamais seule
 * l'information. `enCours` fait tourner l'icône, sauf si l'utilisateur réduit les animations. */
export function StatusBadge({
  libelle,
  ton,
  icone: Icone,
  enCours = false,
}: {
  libelle: string;
  ton: TonStatut;
  icone: LucideIcon;
  enCours?: boolean;
}) {
  return (
    <Badge variant={VARIANTES[ton]}>
      <Icone aria-hidden="true" className={cn(enCours && "motion-safe:animate-spin")} />
      {libelle}
    </Badge>
  );
}
