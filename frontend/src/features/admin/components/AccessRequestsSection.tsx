import { Check, X } from "lucide-react";
import { useId, useState } from "react";
import { ApiError } from "@/shared/api/errors";
import type { AccessRequestView } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  LIBELLES_DOMAINE_RECHERCHE,
  LIBELLES_TYPE_INVESTISSEUR,
} from "@/shared/format/demandeAcces";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { useConfirm } from "@/shared/ui/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Label } from "@/shared/ui/label";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { Textarea } from "@/shared/ui/textarea";
import { useAccessRequests, useDecideAccessRequest } from "../api";

function precision(demande: AccessRequestView): string {
  if (demande.investor_type) return LIBELLES_TYPE_INVESTISSEUR[demande.investor_type];
  if (demande.research_domain) return LIBELLES_DOMAINE_RECHERCHE[demande.research_domain];
  return "—";
}

/** Demandes d'accès Investisseur / Chercheur en attente (tâche 5.10) : approuver envoie le lien
 * d'activation ; refuser exige un motif, transmis au demandeur. Repliée quand il n'y en a aucune. */
export function AccessRequestsSection() {
  const { data: demandes, isError } = useAccessRequests("PENDING_APPROVAL");
  const decider = useDecideAccessRequest();
  const confirm = useConfirm();
  const [aRefuser, setARefuser] = useState<AccessRequestView | null>(null);

  if (demandes !== undefined && demandes.length === 0) return null;

  async function approuver(demande: AccessRequestView) {
    const ok = await confirm({
      title: "Approuver cette demande ?",
      description: `${demande.full_name ?? demande.email} recevra un lien pour créer son mot de passe.`,
      confirmLabel: "Approuver",
    });
    if (ok) decider.mutate({ id: demande.id, decision: "approve" });
  }

  return (
    <Card id="demandes-acces">
      <CardHeader>
        <CardTitle className="text-base">Demandes d’accès</CardTitle>
        <CardDescription>
          Investisseurs et chercheurs inscrits eux-mêmes, en attente de validation.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {isError ? <p className="text-destructive">Impossible de charger les demandes.</p> : null}
        {decider.isError && !aRefuser ? (
          <Alert variant="destructive">
            <AlertDescription>
              {decider.error instanceof ApiError
                ? decider.error.message
                : "La décision n’a pas été enregistrée."}
            </AlertDescription>
          </Alert>
        ) : null}
        {demandes === undefined && !isError ? <CardListSkeleton count={2} /> : null}
        {demandes && demandes.length > 0 ? (
          <ul aria-label="Demandes d’accès en attente" className="divide-y">
            {demandes.map((demande) => (
              <li
                key={demande.id}
                className="flex flex-wrap items-center justify-between gap-3 py-3"
              >
                <div className="min-w-0 space-y-0.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-foreground">
                      {demande.full_name ?? demande.email}
                    </span>
                    <Badge variant="outline">
                      {demande.role === "INVESTOR" ? "Investisseur" : "Chercheur"}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {demande.email} · {demande.organization} · {precision(demande)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Demandée le {new Date(demande.requested_at).toLocaleDateString("fr-FR")}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => approuver(demande)} disabled={decider.isPending}>
                    <Check aria-hidden="true" />
                    Approuver
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setARefuser(demande)}
                    disabled={decider.isPending}
                  >
                    <X aria-hidden="true" />
                    Refuser
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
      <DialogueRefus
        demande={aRefuser}
        onClose={() => setARefuser(null)}
        refuser={(motif) =>
          aRefuser &&
          decider.mutate(
            { id: aRefuser.id, decision: "reject", reason: motif },
            { onSuccess: () => setARefuser(null) },
          )
        }
        enCours={decider.isPending}
        erreur={
          decider.isError && aRefuser
            ? decider.error instanceof ApiError
              ? decider.error.message
              : "Le refus n’a pas été enregistré."
            : null
        }
      />
    </Card>
  );
}

function DialogueRefus({
  demande,
  onClose,
  refuser,
  enCours,
  erreur,
}: {
  demande: AccessRequestView | null;
  onClose: () => void;
  refuser: (motif: string) => void;
  enCours: boolean;
  erreur: string | null;
}) {
  const id = useId();
  const [motif, setMotif] = useState("");
  const vide = motif.trim().length === 0;

  return (
    <Dialog
      open={demande !== null}
      onOpenChange={(ouvert) => {
        if (!ouvert) {
          setMotif("");
          onClose();
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Refuser la demande</DialogTitle>
          <DialogDescription>
            Le motif est envoyé à {demande?.email}. Le demandeur pourra présenter une nouvelle
            demande avec la même adresse.
          </DialogDescription>
        </DialogHeader>
        {erreur ? (
          <Alert variant="destructive">
            <AlertDescription>{erreur}</AlertDescription>
          </Alert>
        ) : null}
        <div className="space-y-2">
          <Label htmlFor={id}>Motif du refus</Label>
          <Textarea
            id={id}
            rows={4}
            maxLength={2000}
            value={motif}
            onChange={(event) => setMotif(event.target.value)}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Annuler
          </Button>
          <Button
            variant="destructive"
            disabled={vide || enCours}
            onClick={() => refuser(motif.trim())}
          >
            Refuser la demande
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
