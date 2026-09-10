import { useState } from "react";
import { ApiError } from "@/shared/api/errors";
import { libelleStatutRattachement, variantStatutRattachement } from "@/shared/format/statutRattachement";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { useAvailableResearchers, useInviteResearcher, useMyResearchers } from "../api";

/** Chercheurs disponibles (jamais rattachés) à inviter, et suivi des rattachements déjà existants
 * — toujours une sélection parmi des comptes réels, jamais une saisie libre d'identité. */
export function ResearchersPage() {
  const { data: disponibles, isLoading: chargementDisponibles } = useAvailableResearchers();
  const { data: rattachements, isLoading: chargementRattachements } = useMyResearchers();
  const inviter = useInviteResearcher();
  const [erreur, setErreur] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Institution"
        title="Chercheurs"
        description="Inviter un chercheur, suivre les invitations en attente, acceptées ou refusées."
      />
      {erreur ? <p className="text-sm text-destructive">{erreur}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-brand-blue">Chercheurs disponibles</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {chargementDisponibles ? <p className="text-brand-grey">Chargement...</p> : null}
          {!chargementDisponibles && disponibles?.length === 0 ? (
            <p className="text-brand-grey">Aucun chercheur disponible à inviter pour l'instant.</p>
          ) : null}
          {disponibles?.map((chercheur) => (
            <div key={chercheur.id} className="flex items-center justify-between gap-3 border-b py-2 last:border-0">
              <div>
                <p className="text-sm font-medium text-brand-blue">{chercheur.nom ?? chercheur.email}</p>
                <p className="text-xs text-brand-grey">{chercheur.email}</p>
              </div>
              <Button
                size="sm"
                disabled={inviter.isPending}
                onClick={() =>
                  inviter.mutate(
                    { chercheur_id: chercheur.id },
                    {
                      onError: (error) =>
                        setErreur(error instanceof ApiError ? error.message : "Échec de l'invitation."),
                    },
                  )
                }
              >
                Inviter
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-brand-blue">Mes rattachements</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {chargementRattachements ? <p className="text-brand-grey">Chargement...</p> : null}
          {!chargementRattachements && rattachements?.length === 0 ? (
            <p className="text-brand-grey">Aucune invitation envoyée pour l'instant.</p>
          ) : null}
          {rattachements?.map((rattachement) => (
            <div key={rattachement.id} className="flex items-center justify-between border-b py-2 text-sm last:border-0">
              <span className="text-brand-grey">
                Invité le {new Date(rattachement.date_invitation).toLocaleDateString("fr-FR")}
              </span>
              <Badge variant={variantStatutRattachement(rattachement.statut)}>
                {libelleStatutRattachement(rattachement.statut)}
              </Badge>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
