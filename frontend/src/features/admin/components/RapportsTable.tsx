import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import type { RapportAdminListe } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleCauseExtraction } from "@/shared/format/causeExtraction";
import { uneDecimale } from "@/shared/format/etatPosition";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import { libelleTypeRapport, titreDeclaration } from "@/shared/format/typeRapport";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { type ColonneTable, DataTable } from "@/shared/ui/data-table";
import { Select } from "@/shared/ui/select";
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
import {
  useAssignReport,
  useFailedExtractionReports,
  useOrphanReportsInValidation,
  useOverdueReports,
  useReportsInValidation,
  useReportsToAssign,
  useRetryExtraction,
  useTableRapports,
  useUtilisateursSelectionnables,
} from "../api";
import { Role } from "../schemas";

export type PerimetreRapports = "tous" | "a-affecter" | "en-validation" | "alertes";

export type Ligne = RapportAdminListe & { alerte?: string };

const MESSAGES_VIDES: Record<PerimetreRapports, string> = {
  tous: "Aucun rapport.",
  "a-affecter": "Aucun rapport en attente d’affectation.",
  "en-validation": "Aucune décision à rendre.",
  alertes:
    "Aucune anomalie : pas d’échec d’extraction, d’audit en retard ni de décision sans avis.",
};

function useLignes(perimetre: PerimetreRapports) {
  const tous = useTableRapports();
  const aAffecter = useReportsToAssign();
  const enValidation = useReportsInValidation();
  const echecs = useFailedExtractionReports();
  const orphelins = useOrphanReportsInValidation();
  const enRetard = useOverdueReports();

  return useMemo(() => {
    if (perimetre === "tous") return { lignes: tous.data as Ligne[] | undefined, ...etat(tous) };
    if (perimetre === "a-affecter")
      return { lignes: aAffecter.data as Ligne[] | undefined, ...etat(aAffecter) };
    if (perimetre === "en-validation")
      return { lignes: enValidation.data as Ligne[] | undefined, ...etat(enValidation) };
    const sources = [
      [echecs, "Échec d’extraction"],
      [enRetard, "Audit en retard"],
      [orphelins, "Décision sans avis d’audit"],
    ] as const;
    const pret = sources.every(([q]) => q.data);
    const lignes = pret
      ? sources.flatMap(([q, alerte]) => (q.data ?? []).map((r): Ligne => ({ ...r, alerte })))
      : undefined;
    return {
      lignes,
      chargement: !pret && !sources.some(([q]) => q.isError),
      erreur: sources.some(([q]) => q.isError),
    };
  }, [perimetre, tous, aAffecter, enValidation, echecs, orphelins, enRetard]);
}

function etat(q: { isLoading: boolean; isError: boolean }) {
  return { chargement: q.isLoading, erreur: q.isError };
}

/** Table des rapports (tâche 5.17) : entreprise, exercice, type et score seulement ; statut,
 * alerte, dates, extraction et actions (affecter, relancer, décider) dans le tiroir. Les quatre
 * onglets de la page Rapports partagent cette table. */
export function RapportsTable({ perimetre }: { perimetre: PerimetreRapports }) {
  const { lignes, chargement, erreur } = useLignes(perimetre);
  const [ouvertId, setOuvertId] = useState<string | null>(null);

  const colonnes = useMemo<ColonneTable<Ligne>[]>(
    () => [
      {
        id: "entreprise",
        entete: "Entreprise",
        masquable: false,
        valeurTri: (r) => r.company_name ?? "",
        cellule: (r) => <span className="font-semibold text-foreground">{r.company_name}</span>,
      },
      {
        id: "exercice",
        entete: "Exercice",
        alignement: "droite",
        valeurTri: (r) => r.fiscal_year,
        cellule: (r) => <span className="font-mono">{r.fiscal_year ?? "—"}</span>,
      },
      {
        id: "type",
        entete: "Type de rapport",
        valeurTri: (r) => libelleTypeRapport(r.type),
        cellule: (r) => libelleTypeRapport(r.type),
      },
      {
        id: "score",
        entete: "Score ESG",
        alignement: "droite",
        valeurTri: (r) => r.official_global_score ?? null,
        cellule: (r) => (
          <span className="font-mono font-semibold">
            {r.official_global_score != null ? uneDecimale(r.official_global_score) : "—"}
          </span>
        ),
      },
    ],
    [],
  );

  const ouvert = lignes?.find((r) => r.id === ouvertId) ?? null;
  const filtres = [
    { id: "type", libelle: "Type", valeur: (r: Ligne) => libelleTypeRapport(r.type) },
    {
      id: "exercice",
      libelle: "Exercice",
      valeur: (r: Ligne) => (r.fiscal_year ? String(r.fiscal_year) : null),
    },
    ...(perimetre === "alertes"
      ? [{ id: "alerte", libelle: "Alerte", valeur: (r: Ligne) => r.alerte ?? null }]
      : []),
  ];

  return (
    <>
      <DataTable
        libelle="Rapports"
        lignes={lignes}
        colonnes={colonnes}
        cle={(r) => `${r.id}-${r.alerte ?? ""}`}
        rechercheDans={(r) =>
          `${r.company_name ?? ""} ${libelleTypeRapport(r.type)} ${r.fiscal_year ?? ""}`
        }
        placeholderRecherche="Entreprise, type, exercice…"
        filtres={filtres}
        triInitial={{ colonne: "entreprise", sens: "asc" }}
        surOuvrir={(r) => setOuvertId(r.id)}
        libelleLigne={(r) => `${r.company_name ?? ""}, ${titreDeclaration(r)}`}
        ligneActive={ouvert ? `${ouvert.id}-${ouvert.alerte ?? ""}` : null}
        chargement={chargement}
        erreur={erreur}
        messageVide={MESSAGES_VIDES[perimetre]}
        nomExport={`rapports-${perimetre}`}
        memoire="admin-rapports"
      />
      <RapportTiroir rapport={ouvert} surFermer={() => setOuvertId(null)} />
    </>
  );
}

function dateFr(iso: string | null | undefined): string | null {
  return iso ? new Date(iso).toLocaleDateString("fr-FR") : null;
}

export function RapportTiroir({
  rapport,
  surFermer,
}: {
  rapport: Ligne | null;
  surFermer: () => void;
}) {
  return (
    <Sheet open={rapport !== null} onOpenChange={(o) => !o && surFermer()}>
      {rapport ? (
        <SheetContent>
          <SheetHeader>
            <SheetTitle>{rapport.company_name}</SheetTitle>
            <SheetDescription>{titreDeclaration(rapport)}</SheetDescription>
            <div className="flex flex-wrap gap-1.5">
              <Badge variant={variantStatutRapport(rapport.status)}>
                {libelleStatutRapport(rapport.status)}
              </Badge>
              {rapport.alerte ? <Badge variant="destructive">{rapport.alerte}</Badge> : null}
            </div>
          </SheetHeader>
          <SheetBody>
            <SheetSection titre="Workflow">
              <SheetFields
                champs={[
                  { libelle: "Statut", valeur: libelleStatutRapport(rapport.status) },
                  { libelle: "Déposé le", valeur: dateFr(rapport.submitted_at) ?? "Non soumis" },
                  { libelle: "Créé le", valeur: dateFr(rapport.created_at) },
                  {
                    libelle: "Version",
                    valeur: <span className="font-mono">{rapport.version}</span>,
                  },
                  {
                    libelle: "Extraction",
                    valeur: rapport.extraction_error
                      ? libelleCauseExtraction(rapport.extraction_error)
                      : rapport.extraction_finished_at
                        ? `Terminée le ${dateFr(rapport.extraction_finished_at)}`
                        : "En attente",
                  },
                ]}
              />
            </SheetSection>
            <SheetSection titre="ESG">
              <SheetFields
                champs={[
                  {
                    libelle: "Score officiel",
                    valeur:
                      rapport.official_global_score != null ? (
                        <span className="font-mono font-semibold">
                          {uneDecimale(rapport.official_global_score)}/100
                        </span>
                      ) : (
                        "Pas encore de score (rapport non validé)"
                      ),
                  },
                  {
                    libelle: "Couverture",
                    valeur:
                      rapport.coverage_rate != null
                        ? `${Math.round(rapport.coverage_rate * 100)} %`
                        : null,
                  },
                  { libelle: "Fichier", valeur: rapport.original_filename },
                ]}
              />
            </SheetSection>
            {rapport.status === "AWAITING_ASSIGNMENT" ? (
              <Affectation rapportId={rapport.id} />
            ) : null}
            {rapport.extraction_error ? <Relance rapportId={rapport.id} /> : null}
          </SheetBody>
          <SheetFooter>
            <Button asChild size="sm">
              <Link to={`/admin/rapports/${rapport.id}`}>
                {rapport.status === "PENDING_DECISION" ? "Rendre la décision" : "Ouvrir le rapport"}
              </Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link to={`/admin/entreprises/${rapport.company_id}`}>Fiche de l’entreprise</Link>
            </Button>
          </SheetFooter>
        </SheetContent>
      ) : null}
    </Sheet>
  );
}

function Affectation({ rapportId }: { rapportId: string }) {
  const { data: auditeurs } = useUtilisateursSelectionnables(Role.AUDITOR);
  const assign = useAssignReport(rapportId);
  const [auditeurId, setAuditeurId] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);

  if (assign.isSuccess) {
    return (
      <Alert variant="success">
        <AlertDescription>Auditeur affecté.</AlertDescription>
      </Alert>
    );
  }
  return (
    <SheetSection titre="Affecter un auditeur">
      <div className="flex flex-wrap gap-2">
        <label htmlFor="affectation-auditeur" className="sr-only">
          Auditeur
        </label>
        <div className="min-w-0 flex-1">
          <Select
            id="affectation-auditeur"
            value={auditeurId}
            onChange={(e) => setAuditeurId(e.target.value)}
            className="h-9"
          >
            <option value="">Choisir un auditeur…</option>
            {(auditeurs ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.name ? `${a.name} — ${a.email}` : a.email}
              </option>
            ))}
          </Select>
        </div>
        <Button
          size="sm"
          disabled={!auditeurId}
          loading={assign.isPending}
          onClick={() => {
            setErreur(null);
            assign.mutate(
              { auditor_id: auditeurId },
              {
                onError: (err) =>
                  setErreur(err instanceof ApiError ? err.message : "Échec de l’affectation."),
              },
            );
          }}
        >
          Affecter
        </Button>
      </div>
      {erreur ? <p className="text-sm text-danger">{erreur}</p> : null}
    </SheetSection>
  );
}

function Relance({ rapportId }: { rapportId: string }) {
  const retry = useRetryExtraction();
  const [erreur, setErreur] = useState<string | null>(null);
  return (
    <SheetSection titre="Extraction">
      {retry.isSuccess ? (
        <p className="text-sm text-success">Relance en cours…</p>
      ) : (
        <Button
          size="sm"
          variant="outline"
          className="w-fit"
          loading={retry.isPending}
          onClick={() => {
            setErreur(null);
            retry.mutate(rapportId, { onError: (e) => setErreur(e.message) });
          }}
        >
          Relancer l’extraction
        </Button>
      )}
      {erreur ? <p className="text-sm text-danger">{erreur}</p> : null}
    </SheetSection>
  );
}
