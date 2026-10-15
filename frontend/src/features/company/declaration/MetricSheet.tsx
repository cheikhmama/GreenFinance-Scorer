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
import { pilierDepuisSlug } from "../esg/taxonomie";
import { libellePreuveVue, type MetriqueVue, metriquesDuRapport } from "../esg/vueMetrique";

const CONFIANCE: Record<ConfidenceLevel, string> = {
  ELEVE: "Élevée",
  MOYEN: "Moyenne",
  FAIBLE: "Faible",
};

function BlocValeur({
  metrique,
  rapportId,
  titre,
}: {
  metrique: MetriqueVue;
  rapportId: string;
  titre: string | null;
}) {
  return (
    <section aria-label={titre ?? undefined} className="space-y-4">
      {titre ? <h3 className="text-sm font-semibold text-foreground">{titre}</h3> : null}
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
    </section>
  );
}

/** Niveau 5 (spec §2.2) : une valeur, sa qualité, sa revue et la page du rapport d'origine où
 * elle figure. Jamais le texte extrait (spec §4.1). Plusieurs lignes peuvent partager un même code
 * (exercices différents) : le tiroir les montre toutes, chacune sous son exercice. */
export function MetricSheet() {
  const { rapportId: segment = "", pilier: slugPilier, famille, code } = useParams();
  const rapportId = idDepuisSlug(segment);
  const pilier = pilierDepuisSlug(slugPilier);
  const { data: metriques, isPending } = useQuery({
    ...rapportQueryOptions(rapportId),
    select: (rapport) =>
      metriquesDuRapport(rapport).filter(
        (m) => m.pilier === pilier && m.famille === famille && m.cle === code,
      ),
  });
  if (isPending) return null;
  const retour = `/company/declarations/${segment}/${slugPilier}/${famille}`;

  if (!metriques || metriques.length === 0) {
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
  const plusieurs = metriques.length > 1;
  return (
    <RouteSheet retour={retour} titre={metriques[0].libelle}>
      <SheetBody>
        {metriques.map((m) => (
          <BlocValeur
            key={m.id}
            metrique={m}
            rapportId={rapportId}
            titre={
              plusieurs ? (m.periode !== null ? `Exercice ${m.periode}` : "Sans exercice") : null
            }
          />
        ))}
      </SheetBody>
    </RouteSheet>
  );
}
