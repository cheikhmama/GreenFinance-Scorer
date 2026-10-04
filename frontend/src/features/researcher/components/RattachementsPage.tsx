import { useMemo, useState } from "react";
import { ApiError } from "@/shared/api/errors";
import type { RattachementPublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  libelleStatutRattachement,
  variantStatutRattachement,
} from "@/shared/format/statutRattachement";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { type ColonneTable, DataTable } from "@/shared/ui/data-table";
import { InitialsAvatar } from "@/shared/ui/initials-avatar";
import { PageHeader } from "@/shared/ui/page-header";
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
import { useAcceptInvitation, useDeclineInvitation, useMyInvitations } from "../api";

const nomInstitution = (r: RattachementPublic) => r.institution_name ?? r.institution_email;
const dateFr = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("fr-FR") : null);

/** Invitations reçues d'institutions — accepter ouvre la voie à une affectation de projet,
 * refuser laisse l'institution libre de réinviter plus tard (voir app/institution/chercheurs.py).
 * Table de données (tâche 5.18) : conditions de collaboration et réponse dans le tiroir. */
export function RattachementsPage() {
  const { data: rattachements, isLoading, isError } = useMyInvitations();
  const [ouvertId, setOuvertId] = useState<string | null>(null);

  const colonnes = useMemo<ColonneTable<RattachementPublic>[]>(
    () => [
      {
        id: "institution",
        entete: "Institution",
        masquable: false,
        valeurTri: nomInstitution,
        cellule: (r) => (
          <span className="flex items-center gap-2.5 font-semibold text-foreground">
            <InitialsAvatar nom={nomInstitution(r)} size="sm" />
            {nomInstitution(r)}
          </span>
        ),
      },
      {
        id: "email",
        entete: "E-mail",
        valeurTri: (r) => r.institution_email,
        cellule: (r) => <span className="text-muted-foreground">{r.institution_email}</span>,
      },
      {
        id: "statut",
        entete: "Statut",
        alignement: "centre",
        valeurTri: (r) => libelleStatutRattachement(r.status),
        cellule: (r) => (
          <Badge variant={variantStatutRattachement(r.status)}>
            {libelleStatutRattachement(r.status)}
          </Badge>
        ),
      },
      {
        id: "invite",
        entete: "Invité le",
        alignement: "droite",
        valeurTri: (r) => r.invited_at,
        cellule: (r) => <span className="font-mono">{dateFr(r.invited_at)}</span>,
      },
    ],
    [],
  );
  const ouvert = rattachements?.find((r) => r.id === ouvertId) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Rattachements"
        description="Invitations reçues d'institutions — un projet ne peut vous être affecté qu'après acceptation."
      />

      <DataTable
        libelle="Invitations reçues"
        lignes={rattachements}
        colonnes={colonnes}
        cle={(r) => r.id}
        rechercheDans={(r) => `${nomInstitution(r)} ${r.institution_email}`}
        placeholderRecherche="Institution, e-mail…"
        filtres={[
          { id: "statut", libelle: "Statut", valeur: (r) => libelleStatutRattachement(r.status) },
        ]}
        triInitial={{ colonne: "invite", sens: "desc" }}
        surOuvrir={(r) => setOuvertId(r.id)}
        libelleLigne={nomInstitution}
        ligneActive={ouvertId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucune invitation reçue pour l’instant."
        nomExport="rattachements"
        memoire="chercheur-rattachements"
      />

      <RattachementTiroir rattachement={ouvert} surFermer={() => setOuvertId(null)} />
    </div>
  );
}

function RattachementTiroir({
  rattachement,
  surFermer,
}: {
  rattachement: RattachementPublic | null;
  surFermer: () => void;
}) {
  const accepter = useAcceptInvitation();
  const refuser = useDeclineInvitation();
  const [erreur, setErreur] = useState<string | null>(null);

  const surErreur = (repli: string) => (err: unknown) =>
    setErreur(err instanceof ApiError ? err.message : repli);

  return (
    <Sheet
      open={rattachement !== null}
      onOpenChange={(o) => {
        if (!o) {
          setErreur(null);
          surFermer();
        }
      }}
    >
      {rattachement ? (
        <SheetContent>
          <SheetHeader>
            <SheetTitle>{nomInstitution(rattachement)}</SheetTitle>
            <SheetDescription>{rattachement.institution_email}</SheetDescription>
            <Badge variant={variantStatutRattachement(rattachement.status)} className="w-fit">
              {libelleStatutRattachement(rattachement.status)}
            </Badge>
          </SheetHeader>
          <SheetBody>
            {erreur ? (
              <Alert variant="destructive">
                <AlertDescription>{erreur}</AlertDescription>
              </Alert>
            ) : null}
            <SheetSection titre="Invitation">
              <SheetFields
                champs={[
                  { libelle: "Invité le", valeur: dateFr(rattachement.invited_at) },
                  { libelle: "Répondu le", valeur: dateFr(rattachement.responded_at) },
                  {
                    libelle: "Conditions de collaboration",
                    valeur: rattachement.collaboration_terms,
                  },
                ]}
              />
            </SheetSection>
          </SheetBody>
          {rattachement.status === "EN_ATTENTE" ? (
            <SheetFooter>
              <Button
                size="sm"
                loading={accepter.isPending}
                disabled={refuser.isPending}
                onClick={() => {
                  setErreur(null);
                  accepter.mutate(rattachement.id, {
                    onError: surErreur("Échec de l’acceptation."),
                  });
                }}
              >
                Accepter
              </Button>
              <Button
                size="sm"
                variant="outline"
                loading={refuser.isPending}
                disabled={accepter.isPending}
                onClick={() => {
                  setErreur(null);
                  refuser.mutate(rattachement.id, { onError: surErreur("Échec du refus.") });
                }}
              >
                Refuser
              </Button>
            </SheetFooter>
          ) : null}
        </SheetContent>
      ) : null}
    </Sheet>
  );
}
