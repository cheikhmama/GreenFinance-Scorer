import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useParams } from "react-router-dom";
import type { ConfidenceLevel } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { formatValeur, libelleMethode } from "@/shared/format/indicateurs";
import { libelleStatutRevue } from "@/shared/format/revue";
import { idDepuisSlug } from "@/shared/format/slug";
import { RouteSheet } from "@/shared/ui/route-sheet";
import { SheetBody, SheetFields, SheetSection } from "@/shared/ui/sheet";
import { rapportQueryOptions } from "../api";
import { libellePreuveVue, metriquesDuRapport } from "../esg/vueMetrique";

const CONFIANCE: Record<ConfidenceLevel, string> = {
  ELEVE: "Élevée",
  MOYEN: "Moyenne",
  FAIBLE: "Faible",
};

/** Niveau 5 (spec §2.2) : une valeur, sa qualité, sa revue et la page du rapport d'origine où
 * elle figure. Jamais le texte extrait (spec §4.1). */
export function MetricSheet() {
  const { rapportId: segment = "", pilier, famille, code } = useParams();
  const rapportId = idDepuisSlug(segment);
  const { data: metrique, isPending } = useQuery({
    ...rapportQueryOptions(rapportId),
    select: (rapport) =>
      metriquesDuRapport(rapport).find((m) => m.cle === code && m.famille === famille) ?? null,
  });
  if (isPending) return null;
  const retour = `/company/declarations/${segment}/${pilier}/${famille}`;

  if (!metrique) {
    return (
      <RouteSheet retour={retour} titre="Indicateur introuvable">
        <SheetBody>
          <p className="text-sm text-muted-foreground">
            Cet indicateur ne figure pas dans cette déclaration.
          </p>
        </SheetBody>
      </RouteSheet>
    );
  }
  return (
    <RouteSheet retour={retour} titre={metrique.libelle}>
      <SheetBody>
        <SheetSection titre="Valeur">
          <SheetFields
            champs={[
              { libelle: "Valeur lue", valeur: formatValeur(metrique.valeur, metrique.unite) },
              { libelle: "Période", valeur: metrique.periode },
              { libelle: "Méthode", valeur: libelleMethode(metrique.methode) },
              {
                libelle: "Confiance",
                valeur: metrique.confiance ? CONFIANCE[metrique.confiance] : null,
              },
            ]}
          />
        </SheetSection>
        <SheetSection titre="Revue de l’auditeur">
          <SheetFields
            champs={[
              {
                libelle: "Statut",
                valeur: metrique.revue ? libelleStatutRevue(metrique.revue) : "Pas encore revue",
              },
              {
                libelle: "Valeur retenue",
                valeur:
                  metrique.valeurAuditee !== null
                    ? formatValeur(metrique.valeurAuditee, metrique.unite)
                    : null,
              },
            ]}
          />
        </SheetSection>
        <SheetSection titre="Source">
          <a
            href={`/api/v1/company/rapports/${rapportId}/fichier#page=${metrique.preuve.pageDebut}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-sm text-foreground underline-offset-2 hover:underline"
          >
            {libellePreuveVue(metrique.preuve)}
            <ExternalLink className="size-3.5" aria-hidden="true" />
          </a>
        </SheetSection>
      </SheetBody>
    </RouteSheet>
  );
}
