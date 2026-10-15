import { useQuery } from "@tanstack/react-query";
import { Navigate, useParams } from "react-router-dom";
import { idDepuisSlug } from "@/shared/format/slug";
import { rapportQueryOptions } from "../api";
import { etatBrouillon } from "../session/etat";
import { DocumentStep } from "./DocumentStep";
import { VerificationStep } from "./VerificationStep";

/** Étapes 3–4, sur le brouillon (spec §3.1). La vérification n'est ouverte qu'à un fichier
 * analysé sans erreur ; une déclaration soumise sans reçu à afficher retourne à sa synthèse —
 * mais l'étape reste montée juste après la soumission, pour montrer le reçu. */
export function DraftStepPage() {
  const { rapportId: segment = "", etape } = useParams();
  const { data: rapport } = useQuery(rapportQueryOptions(idDepuisSlug(segment)));
  if (!rapport) return null;
  if (etape === "verification") {
    if (rapport.submitted_at === null && etatBrouillon(rapport) !== "PRET") {
      return <Navigate to="../document" relative="path" replace />;
    }
    return <VerificationStep rapport={rapport} />;
  }
  if (rapport.submitted_at !== null) return <Navigate to="../.." relative="path" replace />;
  return <DocumentStep rapport={rapport} />;
}
