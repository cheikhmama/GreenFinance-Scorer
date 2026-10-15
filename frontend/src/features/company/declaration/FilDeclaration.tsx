import { useQuery } from "@tanstack/react-query";
import { idDepuisSlug } from "@/shared/format/slug";
import { titreDeclaration } from "@/shared/format/typeRapport";
import { rapportQueryOptions } from "../api";

/** Libellé du fil d'Ariane d'une déclaration — lu dans le cache déjà rempli par la page. */
export function FilDeclaration({ segment }: { segment: string }) {
  const { data } = useQuery(rapportQueryOptions(idDepuisSlug(segment)));
  return <>{data ? titreDeclaration(data) : "Déclaration"}</>;
}
