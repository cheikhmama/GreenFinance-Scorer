import { Fragment } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type {
  DonneeCarboneDetail,
  EntrepriseDetailInvestisseur,
  IndicateurESGDetail,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { formatScore, variantScore } from "@/shared/format/etatPosition";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { useCompareCompanies } from "../api";

const COULEURS = ["#2563eb", "#059669", "#d97706", "#7c3aed"];

function libellePilier(pilier: string): string {
  if (pilier === "ENVIRONNEMENT") return "Environnement (E)";
  if (pilier === "SOCIAL") return "Social (S)";
  return "Gouvernance (G)";
}

function libelleMethode(methode: string): string {
  if (methode === "RAPPORTEE") return "rapportée";
  if (methode === "ESTIMEE") return "estimée";
  return "calculée";
}

/** Étape 2/2 : le résultat, sur sa propre page — jamais mélangé à l'écran de sélection
 * (ComparisonPage), pour éviter le long défilement d'une page qui ferait les deux à la fois. */
export function ComparisonResultsPage() {
  const [searchParams] = useSearchParams();
  const idsParam = searchParams.get("ids") ?? "";
  const selection = idsParam.split(",").filter(Boolean);
  const { data: comparaison, isLoading, isError } = useCompareCompanies(selection);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Investisseur"
        title="Résultat de la comparaison"
        description="Scores ESG et indicateurs détaillés, côte à côte."
        action={
          <Link
            to={`/investor/comparaison?ids=${idsParam}`}
            className="text-sm text-brand-blue underline-offset-2 hover:underline"
          >
            Modifier la sélection
          </Link>
        }
      />

      {selection.length < 2 ? (
        <p className="text-brand-grey">
          Il faut au moins deux entreprises pour une comparaison —{" "}
          <Link to="/investor/comparaison" className="text-brand-blue underline-offset-2 hover:underline">
            retournez à la sélection
          </Link>
          .
        </p>
      ) : null}
      {selection.length >= 2 && isLoading ? (
        <p className="text-brand-grey">Chargement de la comparaison...</p>
      ) : null}
      {selection.length >= 2 && isError ? (
        <p className="text-destructive">Impossible de charger la comparaison.</p>
      ) : null}

      {comparaison && comparaison.length >= 2 ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {comparaison.map((entreprise, index) => (
              <Card
                key={entreprise.id}
                className="gap-3 py-4 shadow-none"
                style={{ borderTopColor: COULEURS[index], borderTopWidth: 3 }}
              >
                <CardContent className="space-y-2 px-5">
                  <div className="flex items-center gap-2">
                    <CompanyAvatar nom={entreprise.nom} logo={entreprise.logo} className="size-8" />
                    <p className="truncate font-medium text-brand-blue">{entreprise.nom}</p>
                  </div>
                  <Badge variant={variantScore(entreprise.score.valeur_globale)}>
                    Score global : {formatScore(entreprise.score.valeur_globale)}
                  </Badge>
                </CardContent>
              </Card>
            ))}
          </div>

          <ComparisonTable entreprises={comparaison} />

          <Card>
            <CardHeader>
              <CardTitle className="text-base text-brand-blue">Radar ESG</CardTitle>
            </CardHeader>
            <CardContent>
              <EsgRadarChart entreprises={comparaison} />
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}

function EsgRadarChart({ entreprises }: { entreprises: EntrepriseDetailInvestisseur[] }) {
  const taille = 280;
  const centre = taille / 2;
  const rayon = taille / 2 - 40;
  const axes = [
    { cle: "score_environnement" as const, label: "E" },
    { cle: "score_social" as const, label: "S" },
    { cle: "score_gouvernance" as const, label: "G" },
  ];

  function point(valeur: number, index: number): [number, number] {
    const angle = -Math.PI / 2 + index * ((2 * Math.PI) / axes.length);
    const r = (Math.max(0, Math.min(100, valeur)) / 100) * rayon;
    return [centre + r * Math.cos(angle), centre + r * Math.sin(angle)];
  }

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
      <svg
        viewBox={`0 0 ${taille} ${taille}`}
        className="w-full max-w-[280px]"
        role="img"
        aria-label="Radar comparant les scores Environnement, Social et Gouvernance des entreprises sélectionnées"
      >
        {[0.25, 0.5, 0.75, 1].map((fraction) => (
          <polygon
            key={fraction}
            points={axes.map((_, i) => point(fraction * 100, i).join(",")).join(" ")}
            fill="none"
            stroke="#e2e8f0"
          />
        ))}
        {axes.map((axe, i) => {
          const [x, y] = point(100, i);
          return <line key={axe.cle} x1={centre} y1={centre} x2={x} y2={y} stroke="#e2e8f0" />;
        })}
        {axes.map((axe, i) => {
          const [x, y] = point(112, i);
          return (
            <text
              key={axe.cle}
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="middle"
              className="fill-brand-grey text-xs font-medium"
            >
              {axe.label}
            </text>
          );
        })}
        {entreprises.map((entreprise, entrepriseIndex) => {
          const contour = axes
            .map((axe, i) => point(entreprise.score[axe.cle] ?? 0, i).join(","))
            .join(" ");
          return (
            <polygon
              key={entreprise.id}
              points={contour}
              fill={COULEURS[entrepriseIndex]}
              fillOpacity={0.12}
              stroke={COULEURS[entrepriseIndex]}
              strokeWidth={2}
            />
          );
        })}
      </svg>
      <ul className="space-y-1.5 text-sm">
        {entreprises.map((entreprise, index) => (
          <li key={entreprise.id} className="flex items-center gap-2">
            <span
              className="size-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: COULEURS[index] }}
              aria-hidden="true"
            />
            {entreprise.nom}
          </li>
        ))}
      </ul>
    </div>
  );
}

interface LigneComparaison {
  categorie: string;
  libelle: string;
  valeurs: Map<string, { valeur: number; unite: string; annee: number; methode: string } | null>;
}

function construireLignesIndicateurs(entreprises: EntrepriseDetailInvestisseur[]): LigneComparaison[] {
  const parCode = new Map<string, { pilier: string; parEntreprise: Map<string, IndicateurESGDetail> }>();
  for (const entreprise of entreprises) {
    for (const indicateur of entreprise.indicateurs) {
      if (!parCode.has(indicateur.code)) {
        parCode.set(indicateur.code, { pilier: indicateur.pilier, parEntreprise: new Map() });
      }
      parCode.get(indicateur.code)?.parEntreprise.set(entreprise.id, indicateur);
    }
  }
  return Array.from(parCode.entries()).map(([code, { pilier, parEntreprise }]) => ({
    categorie: libellePilier(pilier),
    libelle: code,
    valeurs: new Map(
      entreprises.map((entreprise) => {
        const indicateur = parEntreprise.get(entreprise.id);
        return [
          entreprise.id,
          indicateur
            ? {
                valeur: indicateur.valeur,
                unite: indicateur.unite,
                annee: indicateur.preuve.annee,
                methode: indicateur.methode,
              }
            : null,
        ];
      }),
    ),
  }));
}

function construireLignesCarbone(entreprises: EntrepriseDetailInvestisseur[]): LigneComparaison[] {
  const parCle = new Map<string, { libelle: string; parEntreprise: Map<string, DonneeCarboneDetail> }>();
  for (const entreprise of entreprises) {
    for (const donnee of entreprise.donnees_carbone) {
      const cle = `${donnee.scope}-${donnee.categorie_ges ?? ""}`;
      const libelle = `Scope ${donnee.scope}${donnee.categorie_ges ? ` — ${donnee.categorie_ges}` : ""}`;
      if (!parCle.has(cle)) parCle.set(cle, { libelle, parEntreprise: new Map() });
      parCle.get(cle)?.parEntreprise.set(entreprise.id, donnee);
    }
  }
  return Array.from(parCle.values()).map(({ libelle, parEntreprise }) => ({
    categorie: "Carbone",
    libelle,
    valeurs: new Map(
      entreprises.map((entreprise) => {
        const donnee = parEntreprise.get(entreprise.id);
        return [
          entreprise.id,
          donnee
            ? {
                valeur: donnee.valeur_tonnes_co2e,
                unite: "tCO2e",
                annee: donnee.annee,
                methode: donnee.methode,
              }
            : null,
        ] as const;
      }),
    ),
  }));
}

function estComparable(
  valeurs: Map<string, { valeur: number; unite: string; annee: number; methode: string } | null>,
): boolean {
  const presentes = Array.from(valeurs.values()).filter((v) => v !== null);
  if (presentes.length < 2) return false;
  const [reference, ...reste] = presentes;
  return reste.every(
    (v) =>
      v?.unite === reference?.unite && v?.annee === reference?.annee && v?.methode === reference?.methode,
  );
}

function ComparisonTable({ entreprises }: { entreprises: EntrepriseDetailInvestisseur[] }) {
  const lignesFinancieres: LigneComparaison[] = [
    {
      categorie: "Financier",
      libelle: "Montant minimum d'investissement",
      valeurs: new Map(
        entreprises.map((entreprise) => [
          entreprise.id,
          entreprise.montant_minimum_investissement !== null && entreprise.devise_montant_minimum
            ? {
                valeur: entreprise.montant_minimum_investissement,
                unite: entreprise.devise_montant_minimum,
                annee: 0,
                methode: "",
              }
            : null,
        ]),
      ),
    },
  ];

  const lignes = [
    ...construireLignesIndicateurs(entreprises),
    ...construireLignesCarbone(entreprises),
    ...lignesFinancieres,
  ];

  const categories = Array.from(new Set(lignes.map((l) => l.categorie)));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base text-brand-blue">Comparaison détaillée</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-xs text-brand-grey">
          Les valeurs les plus hautes et les plus basses d'une ligne ne sont mises en évidence que
          lorsque toutes les entreprises comparées partagent la même unité, la même période et la
          même méthode — sinon la comparaison ne serait pas fiable.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-brand-grey">
                <th className="py-2 pr-4 font-medium">Indicateur</th>
                {entreprises.map((entreprise) => (
                  <th key={entreprise.id} className="py-2 pr-4 font-medium text-brand-blue">
                    {entreprise.nom}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {categories.map((categorie) => (
                <Fragment key={categorie}>
                  <tr className="border-b bg-slate-50">
                    <td
                      colSpan={entreprises.length + 1}
                      className="py-1.5 pr-4 text-xs font-semibold uppercase tracking-wide text-brand-grey"
                    >
                      {categorie}
                    </td>
                  </tr>
                  {lignes
                    .filter((ligne) => ligne.categorie === categorie)
                    .map((ligne) => {
                      const comparable = estComparable(ligne.valeurs);
                      const valeursPresentes = Array.from(ligne.valeurs.values()).filter(
                        (v) => v !== null,
                      ) as { valeur: number; unite: string; annee: number; methode: string }[];
                      const max = comparable ? Math.max(...valeursPresentes.map((v) => v.valeur)) : null;
                      const min = comparable ? Math.min(...valeursPresentes.map((v) => v.valeur)) : null;
                      return (
                        <tr key={`${categorie}-${ligne.libelle}`} className="border-b last:border-0">
                          <td className="py-2 pr-4 text-brand-grey">{ligne.libelle}</td>
                          {entreprises.map((entreprise) => {
                            const cellule = ligne.valeurs.get(entreprise.id) ?? null;
                            if (!cellule) {
                              return (
                                <td key={entreprise.id} className="py-2 pr-4 text-brand-grey">
                                  Non disponible
                                </td>
                              );
                            }
                            const estExtreme =
                              comparable && (cellule.valeur === max || cellule.valeur === min);
                            return (
                              <td
                                key={entreprise.id}
                                className={`py-2 pr-4 ${estExtreme ? "font-semibold text-brand-blue" : ""}`}
                              >
                                {cellule.valeur.toLocaleString("fr-FR")} {cellule.unite}
                                {cellule.annee > 0 ? (
                                  <span className="ml-1 text-xs text-brand-grey">
                                    ({cellule.annee}
                                    {cellule.methode ? `, ${libelleMethode(cellule.methode)}` : ""})
                                  </span>
                                ) : null}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
