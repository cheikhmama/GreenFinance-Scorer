import { Download, Info, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { RapportESGPublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { PHASES_DECLARATION, phaseDeclaration } from "@/shared/format/phaseDeclaration";
import { creerSlug } from "@/shared/format/slug";
import { libelleTypeRapport, titreDeclaration } from "@/shared/format/typeRapport";
import { PageShell } from "@/shared/layout/PageShell";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { type ColonneTable, DataTable } from "@/shared/ui/data-table";
import { PhaseProgress } from "@/shared/ui/phase-progress";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFields,
  SheetFooter,
  SheetHeader,
  SheetSection,
  SheetTitle,
} from "@/shared/ui/sheet";
import { Skeleton } from "@/shared/ui/skeleton";
import { useActualisationSurNotification, useCompanyReports } from "../api";
import { StatutDeclaration } from "../declaration/StatutDeclaration";
import { etapeReprise, libelleExercice, separerDeclarations } from "../session/etat";

function StatutEntreprise({ rapport }: { rapport: RapportESGPublic }) {
  return <StatutDeclaration rapport={rapport} />;
}

function base(rapport: RapportESGPublic) {
  return `/company/declarations/${creerSlug(titreDeclaration(rapport), rapport.id)}`;
}

function date(iso: string | null) {
  return iso ? new Date(iso).toLocaleDateString("fr-FR") : "—";
}

function score(rapport: RapportESGPublic) {
  return rapport.official_global_score != null
    ? `${rapport.official_global_score.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}/100`
    : "—";
}

/** Mes déclarations (tâche 5.9) : l'action « Nouvelle déclaration » dans l'en-tête, la règle
 * « une seule déclaration à la fois » en bandeau, les déclarations en cours avec leur progression,
 * puis l'historique en table de données (tâche 5.18) : couverture, empreinte du fichier et PDF de
 * synthèse dans le tiroir de chaque ligne. */
export function CompanyDeclarationsPage() {
  useActualisationSurNotification();
  const { data: rapports, isPending, isError } = useCompanyReports();
  const { enCours, historique, sessionBloquante } = separerDeclarations(rapports ?? []);

  return (
    <PageShell
      title="Mes déclarations"
      description="Préparez, soumettez et suivez vos déclarations ESG par exercice."
      actions={
        sessionBloquante !== undefined || !rapports ? (
          <Button disabled aria-describedby={sessionBloquante ? "raison-blocage" : undefined}>
            <Plus />
            Nouvelle déclaration
          </Button>
        ) : (
          <Button asChild>
            <Link to="nouvelle/exercice">
              <Plus />
              Nouvelle déclaration
            </Link>
          </Button>
        )
      }
    >
      {sessionBloquante ? (
        <Alert id="raison-blocage" role="note" className="bg-muted/50">
          <Info className="text-primary" aria-hidden="true" />
          <AlertDescription>
            <p>
              <span className="font-medium text-foreground">Une seule déclaration à la fois.</span>{" "}
              Terminez la déclaration {titreDeclaration(sessionBloquante)} avant d’en ouvrir une
              autre.
            </p>
          </AlertDescription>
        </Alert>
      ) : null}

      {isPending ? <Skeleton className="h-40 w-full" /> : null}
      {isError ? (
        <p className="text-sm text-destructive">Impossible de charger vos déclarations.</p>
      ) : null}

      {rapports ? (
        <section aria-labelledby="titre-en-cours" className="space-y-3">
          <h2 id="titre-en-cours" className="text-lg font-semibold tracking-tight text-foreground">
            En cours
          </h2>
          {enCours.length === 0 ? (
            <Card className="py-4">
              <CardContent className="px-5 text-sm text-muted-foreground">
                Aucune déclaration en cours. Ouvrez-en une avec « Nouvelle déclaration ».
              </CardContent>
            </Card>
          ) : (
            <ul className="space-y-3">
              {enCours.map((rapport) => (
                <li key={rapport.id}>
                  <Card className="gap-4 py-5">
                    <CardContent className="space-y-4 px-5">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-foreground">
                            {libelleExercice(rapport.fiscal_year)}
                          </span>
                          <span className="text-sm text-muted-foreground">
                            {titreDeclaration(rapport)}
                          </span>
                          <StatutEntreprise rapport={rapport} />
                        </div>
                        <Button asChild variant="outline" size="sm">
                          <Link
                            to={
                              rapport.submitted_at === null
                                ? `${base(rapport)}/brouillon/${etapeReprise(rapport)}`
                                : base(rapport)
                            }
                          >
                            Ouvrir
                          </Link>
                        </Button>
                      </div>
                      <PhaseProgress
                        etapes={PHASES_DECLARATION}
                        courante={phaseDeclaration(rapport).index}
                      />
                    </CardContent>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {rapports ? <Historique rapports={historique} /> : null}
    </PageShell>
  );
}

function Historique({ rapports }: { rapports: RapportESGPublic[] }) {
  const [ouvertId, setOuvertId] = useState<string | null>(null);
  const colonnes = useMemo<ColonneTable<RapportESGPublic>[]>(
    () => [
      {
        id: "exercice",
        entete: "Exercice",
        masquable: false,
        valeurTri: (r) => r.fiscal_year,
        cellule: (r) => (
          <span className="font-semibold text-foreground">{libelleExercice(r.fiscal_year)}</span>
        ),
      },
      {
        id: "type",
        entete: "Type de rapport",
        valeurTri: (r) => libelleTypeRapport(r.type),
        cellule: (r) => libelleTypeRapport(r.type),
      },
      {
        id: "statut",
        entete: "Statut",
        alignement: "centre",
        valeurTri: (r) => phaseDeclaration(r).libelle,
        valeurExport: (r) => phaseDeclaration(r).libelle,
        cellule: (r) => <StatutEntreprise rapport={r} />,
      },
      {
        id: "soumis",
        entete: "Soumis le",
        alignement: "droite",
        valeurTri: (r) => r.submitted_at,
        cellule: (r) => <span className="font-mono">{date(r.submitted_at)}</span>,
      },
      {
        id: "score",
        entete: "Score officiel",
        alignement: "droite",
        valeurTri: (r) => r.official_global_score ?? null,
        valeurExport: (r) => r.official_global_score ?? null,
        cellule: (r) => <span className="font-mono font-semibold tabular-nums">{score(r)}</span>,
      },
    ],
    [],
  );
  const ouvert = rapports.find((r) => r.id === ouvertId) ?? null;

  return (
    <section aria-labelledby="titre-historique" className="space-y-3">
      <h2 id="titre-historique" className="text-lg font-semibold tracking-tight text-foreground">
        Historique
      </h2>
      <DataTable
        libelle="Historique des déclarations"
        lignes={rapports}
        colonnes={colonnes}
        cle={(r) => r.id}
        rechercheDans={(r) => `${libelleExercice(r.fiscal_year)} ${titreDeclaration(r)}`}
        placeholderRecherche="Exercice, type…"
        filtres={[
          {
            id: "statut",
            libelle: "Statut",
            valeur: (r) => phaseDeclaration(r).libelle,
          },
          { id: "type", libelle: "Type", valeur: (r) => libelleTypeRapport(r.type) },
        ]}
        triInitial={{ colonne: "exercice", sens: "desc" }}
        surOuvrir={(r) => setOuvertId(r.id)}
        libelleLigne={(r) => `${libelleExercice(r.fiscal_year)}, ${titreDeclaration(r)}`}
        ligneActive={ouvertId}
        messageVide="Aucune déclaration close pour l’instant."
        nomExport="historique-declarations"
        memoire="company-historique"
      />
      <Sheet open={ouvert !== null} onOpenChange={(o) => !o && setOuvertId(null)}>
        {ouvert ? (
          <SheetContent>
            <SheetHeader>
              <SheetTitle>{libelleExercice(ouvert.fiscal_year)}</SheetTitle>
              <SheetDescription>{titreDeclaration(ouvert)}</SheetDescription>
              <div className="flex">
                <StatutEntreprise rapport={ouvert} />
              </div>
            </SheetHeader>
            <SheetBody>
              <SheetSection titre="Résultat">
                <SheetFields
                  champs={[
                    {
                      libelle: "Score officiel",
                      valeur: <span className="font-mono font-semibold">{score(ouvert)}</span>,
                    },
                    {
                      libelle: "Couverture",
                      valeur:
                        ouvert.coverage_rate != null
                          ? `${Math.round(ouvert.coverage_rate * 100)} %`
                          : null,
                    },
                    {
                      libelle: "Synthèse",
                      valeur: ouvert.synthesis_available ? (
                        <a
                          href={`/api/v1/company/rapports/${ouvert.id}/synthese/fichier`}
                          className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
                        >
                          <Download className="size-4" aria-hidden="true" />
                          PDF
                        </a>
                      ) : null,
                    },
                  ]}
                />
              </SheetSection>
              <SheetSection titre="Dépôt">
                <SheetFields
                  champs={[
                    { libelle: "Soumis le", valeur: date(ouvert.submitted_at) },
                    {
                      libelle: "Version",
                      valeur: <span className="font-mono">{ouvert.version}</span>,
                    },
                    { libelle: "Fichier", valeur: ouvert.original_filename },
                    {
                      libelle: "SHA-256",
                      valeur: ouvert.checksum_sha256 ? (
                        <code
                          className="font-mono text-xs text-muted-foreground"
                          title={ouvert.checksum_sha256}
                        >
                          {ouvert.checksum_sha256.slice(0, 8)}…{ouvert.checksum_sha256.slice(-4)}
                        </code>
                      ) : null,
                    },
                  ]}
                />
              </SheetSection>
            </SheetBody>
            <SheetFooter>
              <Button asChild size="sm">
                <Link
                  to={`/company/declarations/${creerSlug(titreDeclaration(ouvert), ouvert.id)}`}
                >
                  Voir la déclaration
                </Link>
              </Button>
            </SheetFooter>
          </SheetContent>
        ) : null}
      </Sheet>
    </section>
  );
}
