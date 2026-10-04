import { Fragment } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type {
  DonneeCarboneDetail,
  EntrepriseDetailInvestisseur,
  IndicateurESGDetail,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { formatScore, variantScore } from "@/shared/format/etatPosition";
import { libelleIndicateur, libelleScope } from "@/shared/format/indicateurs";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
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
        title="Résultat de la comparaison"
        description="Scores ESG et indicateurs détaillés, côte à côte."
        action={
          <Link
            to={`/investor/comparaison?ids=${idsParam}`}
            className="text-sm text-foreground underline-offset-2 hover:underline"
          >
            Modifier la sélection
          </Link>
        }
      />

      {selection.length < 2 ? (
        <p className="text-muted-foreground">
          Il faut au moins deux entreprises pour une comparaison —{" "}
          <Link
            to="/investor/comparaison"
            className="text-foreground underline-offset-2 hover:underline"
          >
            retournez à la sélection
          </Link>
          .
        </p>
      ) : null}
      {selection.length >= 2 && isLoading ? (
        <p className="text-muted-foreground">Chargement de la comparaison...</p>
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
                    <CompanyAvatar
                      nom={entreprise.name}
                      logo={entreprise.logo}
                      className="size-8"
                    />
                    <p className="truncate font-medium text-foreground">{entreprise.name}</p>
                  </div>
                  <Badge variant={variantScore(entreprise.score.global_score)}>
                    Score global : {formatScore(entreprise.score.global_score)}
                  </Badge>
                </CardContent>
              </Card>
            ))}
          </div>

          <ComparisonTable entreprises={comparaison} />

          <Card>
            <CardHeader>
              <CardTitle className="text-base text-foreground">Radar ESG</CardTitle>
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
    { cle: "environmental_score" as const, label: "E" },
    { cle: "social_score" as const, label: "S" },
    { cle: "governance_score" as const, label: "G" },
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
            {entreprise.name}
          </li>
        ))}
      </ul>
    </div>
  );
}

interface LigneComparaison {
  categorie: string;
  libelle: string;
  valeurs: Map<string, { value: number; unit: string; year: number; method: string } | null>;
}

function construireLignesIndicateurs(
  entreprises: EntrepriseDetailInvestisseur[],
): LigneComparaison[] {
  const parCode = new Map<
    string,
    { pillar: string; parEntreprise: Map<string, IndicateurESGDetail> }
  >();
  for (const entreprise of entreprises) {
    for (const indicateur of entreprise.metrics) {
      if (!parCode.has(indicateur.metric_code)) {
        parCode.set(indicateur.metric_code, {
          pillar: indicateur.pillar,
          parEntreprise: new Map(),
        });
      }
      parCode.get(indicateur.metric_code)?.parEntreprise.set(entreprise.id, indicateur);
    }
  }
  return Array.from(parCode.entries()).map(([code, { pillar, parEntreprise }]) => ({
    categorie: libellePilier(pillar),
    libelle: libelleIndicateur(code),
    valeurs: new Map(
      entreprises.map((entreprise) => {
        const indicateur = parEntreprise.get(entreprise.id);
        return [
          entreprise.id,
          indicateur
            ? {
                value: indicateur.value,
                unit: indicateur.unit,
                year: indicateur.proof.year,
                method: indicateur.method,
              }
            : null,
        ];
      }),
    ),
  }));
}

function construireLignesCarbone(entreprises: EntrepriseDetailInvestisseur[]): LigneComparaison[] {
  const parCle = new Map<
    string,
    { libelle: string; parEntreprise: Map<string, DonneeCarboneDetail> }
  >();
  for (const entreprise of entreprises) {
    for (const donnee of entreprise.carbon_data) {
      const cle = `${donnee.scope}-${donnee.ghg_category ?? ""}`;
      const libelle = libelleScope(donnee.scope, donnee.ghg_category);
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
                value: donnee.tonnes_co2e,
                unit: "tCO2e",
                year: donnee.year,
                method: donnee.method,
              }
            : null,
        ] as const;
      }),
    ),
  }));
}

function estComparable(
  valeurs: Map<string, { value: number; unit: string; year: number; method: string } | null>,
): boolean {
  const presentes = Array.from(valeurs.values()).filter((v) => v !== null);
  if (presentes.length < 2) return false;
  const [reference, ...reste] = presentes;
  return reste.every(
    (v) =>
      v?.unit === reference?.unit && v?.year === reference?.year && v?.method === reference?.method,
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
          entreprise.minimum_investment_amount !== null && entreprise.minimum_investment_currency
            ? {
                value: entreprise.minimum_investment_amount,
                unit: entreprise.minimum_investment_currency,
                year: 0,
                method: "",
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
        <CardTitle className="text-base text-foreground">Comparaison détaillée</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-xs text-muted-foreground">
          Les valeurs les plus hautes et les plus basses d'une ligne ne sont mises en évidence que
          lorsque toutes les entreprises comparées partagent la même unité, la même période et la
          même méthode — sinon la comparaison ne serait pas fiable.
        </p>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Indicateur</TableHead>
              {entreprises.map((entreprise) => (
                <TableHead key={entreprise.id} className="text-foreground">
                  {entreprise.name}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {categories.map((categorie) => (
              <Fragment key={categorie}>
                <TableRow className="bg-muted/50">
                  <TableCell
                    colSpan={entreprises.length + 1}
                    className="py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                  >
                    {categorie}
                  </TableCell>
                </TableRow>
                {lignes
                  .filter((ligne) => ligne.categorie === categorie)
                  .map((ligne) => {
                    const comparable = estComparable(ligne.valeurs);
                    const valeursPresentes = Array.from(ligne.valeurs.values()).filter(
                      (v) => v !== null,
                    ) as { value: number; unit: string; year: number; method: string }[];
                    const max = comparable
                      ? Math.max(...valeursPresentes.map((v) => v.value))
                      : null;
                    const min = comparable
                      ? Math.min(...valeursPresentes.map((v) => v.value))
                      : null;
                    return (
                      <TableRow key={`${categorie}-${ligne.libelle}`}>
                        <TableCell className="text-muted-foreground">{ligne.libelle}</TableCell>
                        {entreprises.map((entreprise) => {
                          const cellule = ligne.valeurs.get(entreprise.id) ?? null;
                          if (!cellule) {
                            return (
                              <TableCell key={entreprise.id} className="text-muted-foreground">
                                Non disponible
                              </TableCell>
                            );
                          }
                          const estExtreme =
                            comparable && (cellule.value === max || cellule.value === min);
                          return (
                            <TableCell
                              key={entreprise.id}
                              className={`py-2 pr-4 ${estExtreme ? "font-semibold text-foreground" : ""}`}
                            >
                              {cellule.value.toLocaleString("fr-FR")} {cellule.unit}
                              {cellule.year > 0 ? (
                                <span className="ml-1 text-xs text-muted-foreground">
                                  ({cellule.year}
                                  {cellule.method ? `, ${libelleMethode(cellule.method)}` : ""})
                                </span>
                              ) : null}
                            </TableCell>
                          );
                        })}
                      </TableRow>
                    );
                  })}
              </Fragment>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
