import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import type { EntrepriseAdmin } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { uneDecimale } from "@/shared/format/etatPosition";
import { libellePays } from "@/shared/format/pays";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import {
  libelleStatutInscription,
  variantStatutInscription,
} from "@/shared/format/statutInscription";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { useConfirm } from "@/shared/ui/confirm-dialog";
import { type ColonneTable, DataTable } from "@/shared/ui/data-table";
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
  useIdsEntreprisesARepublier,
  useIdsEntreprisesPubliables,
  usePublishCompany,
  useReactivateCompany,
  useSuspendCompany,
  useTableEntreprises,
  useValidateReport,
} from "../api";

export type PerimetreEntreprises = "toutes" | "publiables" | "a-republier";

const MESSAGES_VIDES: Record<PerimetreEntreprises, string> = {
  toutes: "Aucune entreprise inscrite.",
  publiables: "Aucune entreprise prête à être publiée.",
  "a-republier": "Aucune entreprise à republier.",
};

/** Table des entreprises (tâche 5.17) : identité, secteur, pays et score officiel seulement ;
 * statut d'inscription, publication, dernier rapport et actions sont dans le tiroir. Les trois
 * onglets « inscrites », « publiables » et « à republier » partagent cette table — seul le
 * périmètre des lignes change. */
export function EntreprisesTable({ perimetre }: { perimetre: PerimetreEntreprises }) {
  const entreprises = useTableEntreprises();
  const publiables = useIdsEntreprisesPubliables();
  const aRepublier = useIdsEntreprisesARepublier();
  const [ouverteId, setOuverteId] = useState<string | null>(null);

  const lignes = useMemo(() => {
    if (!entreprises.data) return undefined;
    if (perimetre === "publiables") {
      return publiables.data
        ? entreprises.data.filter((e) => publiables.data.has(e.id))
        : undefined;
    }
    if (perimetre === "a-republier") {
      return aRepublier.data
        ? entreprises.data.filter((e) => aRepublier.data.has(e.id))
        : undefined;
    }
    return entreprises.data;
  }, [entreprises.data, publiables.data, aRepublier.data, perimetre]);

  const colonnes = useMemo<ColonneTable<EntrepriseAdmin>[]>(
    () => [
      {
        id: "nom",
        entete: "Entreprise",
        masquable: false,
        valeurTri: (e) => e.name,
        cellule: (e) => (
          <span className="flex items-center gap-2.5 font-semibold text-foreground">
            <CompanyAvatar nom={e.name} logo={e.logo} className="size-6 shrink-0 text-[10px]" />
            {e.name}
          </span>
        ),
      },
      {
        id: "secteur",
        entete: "Secteur",
        valeurTri: (e) => e.sector,
        cellule: (e) => <span className="text-muted-foreground">{e.sector}</span>,
      },
      {
        id: "pays",
        entete: "Pays",
        valeurTri: (e) => libellePays(e.country),
        cellule: (e) => libellePays(e.country),
      },
      {
        id: "score",
        entete: "Score officiel",
        alignement: "droite",
        valeurTri: (e) => e.official_global_score ?? null,
        cellule: (e) => (
          <span className="font-mono font-semibold tabular-nums">
            {e.official_global_score != null ? uneDecimale(e.official_global_score) : "—"}
          </span>
        ),
      },
    ],
    [],
  );

  const ouverte = lignes?.find((e) => e.id === ouverteId) ?? null;

  return (
    <>
      <DataTable
        libelle="Entreprises"
        lignes={lignes}
        colonnes={colonnes}
        cle={(e) => e.id}
        rechercheDans={(e) => `${e.name} ${e.sector} ${libellePays(e.country)}`}
        placeholderRecherche="Nom, secteur, pays…"
        filtres={[
          { id: "secteur", libelle: "Secteur", valeur: (e) => e.sector },
          { id: "pays", libelle: "Pays", valeur: (e) => libellePays(e.country) },
        ]}
        triInitial={{ colonne: "nom", sens: "asc" }}
        surOuvrir={(e) => setOuverteId(e.id)}
        libelleLigne={(e) => e.name}
        ligneActive={ouverteId}
        chargement={entreprises.isLoading || (perimetre !== "toutes" && !lignes)}
        erreur={entreprises.isError || publiables.isError || aRepublier.isError}
        messageVide={MESSAGES_VIDES[perimetre]}
        nomExport={`entreprises-${perimetre}`}
        memoire="admin-entreprises"
      />
      <EntrepriseTiroir
        entreprise={ouverte}
        publiable={!!ouverte && (publiables.data?.has(ouverte.id) ?? false)}
        aRepublier={!!ouverte && (aRepublier.data?.has(ouverte.id) ?? false)}
        surFermer={() => setOuverteId(null)}
      />
    </>
  );
}

function EntrepriseTiroir({
  entreprise,
  publiable,
  aRepublier,
  surFermer,
}: {
  entreprise: EntrepriseAdmin | null;
  publiable: boolean;
  aRepublier: boolean;
  surFermer: () => void;
}) {
  const suspend = useSuspendCompany();
  const reactivate = useReactivateCompany();
  const publish = usePublishCompany();
  const validate = useValidateReport(entreprise?.latest_report_id ?? "");
  const confirm = useConfirm();
  const [erreur, setErreur] = useState<string | null>(null);

  const surErreur = (repli: string) => (err: unknown) =>
    setErreur(err instanceof ApiError ? err.message : repli);

  async function suspendre(e: EntrepriseAdmin) {
    const confirme = await confirm({
      title: "Suspendre cette entreprise ?",
      description: `${e.name} ne pourra plus déposer de nouveau rapport tant qu'elle reste suspendue. Vous pourrez la réactiver à tout moment.`,
      confirmLabel: "Suspendre",
    });
    if (!confirme) return;
    setErreur(null);
    suspend.mutate(e.id, { onError: surErreur("Échec de la suspension.") });
  }

  return (
    <Sheet
      open={entreprise !== null}
      onOpenChange={(ouvert) => {
        if (!ouvert) {
          setErreur(null);
          surFermer();
        }
      }}
    >
      {entreprise ? (
        <SheetContent>
          <SheetHeader>
            <div className="flex items-start gap-3">
              <CompanyAvatar
                nom={entreprise.name}
                logo={entreprise.logo}
                className="size-11 shrink-0"
              />
              <div className="flex min-w-0 flex-col gap-1.5">
                <SheetTitle>{entreprise.name}</SheetTitle>
                <SheetDescription>
                  {entreprise.sector} · {libellePays(entreprise.country)}
                </SheetDescription>
                <div className="flex flex-wrap gap-1.5">
                  <Badge variant={entreprise.published_at ? "success" : "outline"}>
                    {entreprise.published_at ? "Publiée" : "Non publiée"}
                  </Badge>
                  {entreprise.latest_report_status ? (
                    <Badge variant={variantStatutRapport(entreprise.latest_report_status)}>
                      {libelleStatutRapport(entreprise.latest_report_status)}
                    </Badge>
                  ) : (
                    <Badge variant="secondary">Aucun rapport</Badge>
                  )}
                </div>
              </div>
            </div>
          </SheetHeader>
          <SheetBody>
            {erreur ? (
              <Alert variant="destructive">
                <AlertDescription>{erreur}</AlertDescription>
              </Alert>
            ) : null}
            <SheetSection titre="Workflow et ESG">
              <SheetFields
                champs={[
                  {
                    libelle: "Dernier rapport",
                    valeur: entreprise.latest_report_status ? (
                      <Badge variant={variantStatutRapport(entreprise.latest_report_status)}>
                        {libelleStatutRapport(entreprise.latest_report_status)}
                      </Badge>
                    ) : (
                      "Aucun rapport déposé"
                    ),
                  },
                  {
                    libelle: "Rapports déposés",
                    valeur: <span className="font-mono">{entreprise.report_count}</span>,
                  },
                  {
                    libelle: "Score officiel",
                    valeur:
                      entreprise.official_global_score != null ? (
                        <span className="font-mono font-semibold">
                          {uneDecimale(entreprise.official_global_score)}/100
                        </span>
                      ) : (
                        "Pas encore de rapport validé"
                      ),
                  },
                  {
                    libelle: "Publication",
                    valeur: entreprise.published_at
                      ? `Publiée le ${new Date(entreprise.published_at).toLocaleDateString("fr-FR")}`
                      : publiable
                        ? "Prête à être publiée"
                        : "Non publiée",
                  },
                  ...(aRepublier
                    ? [
                        {
                          libelle: "Republication",
                          valeur: "Un rapport validé est plus récent que la fiche publiée",
                        },
                      ]
                    : []),
                ]}
              />
            </SheetSection>
            <SheetSection titre="Compte">
              <SheetFields
                champs={[
                  {
                    libelle: "Inscription",
                    valeur: (
                      <Badge variant={variantStatutInscription(entreprise.status)}>
                        {libelleStatutInscription(entreprise.status)}
                      </Badge>
                    ),
                  },
                  {
                    libelle: "Compte lié",
                    valeur: entreprise.owner_user_id ? "Oui" : "Aucun compte",
                  },
                  { libelle: "Site officiel", valeur: entreprise.website },
                  {
                    libelle: "ISIN · LEI",
                    valeur: [entreprise.isin, entreprise.lei].filter(Boolean).join(" · ") || null,
                  },
                ]}
              />
            </SheetSection>
            <SheetSection titre="Audit">
              <Link
                to={`/admin/journal-audit?concerne=${entreprise.id}`}
                className="text-sm font-semibold"
              >
                Journal d’audit de cette entreprise
              </Link>
            </SheetSection>
          </SheetBody>
          <SheetFooter>
            <Button asChild size="sm">
              <Link to={`/admin/entreprises/${entreprise.id}`}>Ouvrir la fiche</Link>
            </Button>
            {entreprise.latest_report_id ? (
              <Button asChild size="sm" variant="outline">
                <Link to={`/admin/rapports/${entreprise.latest_report_id}`}>Dernier rapport</Link>
              </Button>
            ) : null}
            {publiable || aRepublier ? (
              <Button
                size="sm"
                variant="subtle"
                loading={publish.isPending}
                onClick={() => {
                  setErreur(null);
                  publish.mutate(entreprise.id, { onError: surErreur("Échec de la publication.") });
                }}
              >
                {aRepublier ? "Republier" : "Publier"}
              </Button>
            ) : null}
            {entreprise.latest_report_status === "PENDING_DECISION" &&
            entreprise.latest_report_id ? (
              <Button
                size="sm"
                variant="subtle"
                loading={validate.isPending}
                onClick={() => {
                  setErreur(null);
                  validate.mutate(
                    { comment: null },
                    { onError: surErreur("Échec de la validation.") },
                  );
                }}
              >
                Valider le rapport
              </Button>
            ) : null}
            {entreprise.status === "ACTIVE" ? (
              <Button
                size="sm"
                variant="destructive-outline"
                loading={suspend.isPending}
                onClick={() => suspendre(entreprise)}
              >
                Suspendre
              </Button>
            ) : null}
            {entreprise.status === "SUSPENDED" ? (
              <Button
                size="sm"
                variant="outline"
                loading={reactivate.isPending}
                onClick={() => {
                  setErreur(null);
                  reactivate.mutate(entreprise.id, {
                    onError: surErreur("Échec de la réactivation."),
                  });
                }}
              >
                Réactiver
              </Button>
            ) : null}
          </SheetFooter>
        </SheetContent>
      ) : null}
    </Sheet>
  );
}
