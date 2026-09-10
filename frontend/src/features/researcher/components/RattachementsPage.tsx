import { ApiError } from "@/shared/api/errors";
import { libelleStatutRattachement, variantStatutRattachement } from "@/shared/format/statutRattachement";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { useAcceptInvitation, useDeclineInvitation, useMyInvitations } from "../api";
import { useState } from "react";

/** Invitations reçues d'institutions — accepter ouvre la voie à une affectation de projet,
 * refuser laisse l'institution libre de réinviter plus tard (voir app/institution/chercheurs.py). */
export function RattachementsPage() {
  const { data: rattachements, isLoading, isError } = useMyInvitations();
  const accepter = useAcceptInvitation();
  const refuser = useDeclineInvitation();
  const [erreur, setErreur] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Chercheur"
        title="Rattachements"
        description="Invitations reçues d'institutions — un projet ne peut vous être affecté qu'après acceptation."
      />

      {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
      {isError ? <p className="text-destructive">Impossible de charger les invitations.</p> : null}
      {erreur ? <p className="text-sm text-destructive">{erreur}</p> : null}
      {!isLoading && !isError && rattachements?.length === 0 ? (
        <p className="text-brand-grey">Aucune invitation reçue pour l'instant.</p>
      ) : null}

      <div className="space-y-3">
        {rattachements?.map((rattachement) => (
          <Card key={rattachement.id}>
            <CardContent className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <Badge variant={variantStatutRattachement(rattachement.statut)}>
                  {libelleStatutRattachement(rattachement.statut)}
                </Badge>
                <span className="text-sm text-brand-grey">
                  Invité le {new Date(rattachement.date_invitation).toLocaleDateString("fr-FR")}
                </span>
              </div>
              {rattachement.statut === "EN_ATTENTE" ? (
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    disabled={accepter.isPending}
                    onClick={() =>
                      accepter.mutate(rattachement.id, {
                        onError: (err) =>
                          setErreur(err instanceof ApiError ? err.message : "Échec de l'acceptation."),
                      })
                    }
                  >
                    Accepter
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={refuser.isPending}
                    onClick={() =>
                      refuser.mutate(rattachement.id, {
                        onError: (err) =>
                          setErreur(err instanceof ApiError ? err.message : "Échec du refus."),
                      })
                    }
                  >
                    Refuser
                  </Button>
                </div>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
