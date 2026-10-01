import { zodResolver } from "@hookform/resolvers/zod";
import { UserCheck, Users } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { ApiError } from "@/shared/api/errors";
import {
  libelleStatutRattachement,
  variantStatutRattachement,
} from "@/shared/format/statutRattachement";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/ui/dialog";
import { EmptyState } from "@/shared/ui/empty-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { InitialsAvatar } from "@/shared/ui/initials-avatar";
import { PageHeader } from "@/shared/ui/page-header";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { Textarea } from "@/shared/ui/textarea";
import { useAvailableResearchers, useInviteResearcher, useMyResearchers } from "../api";
import { type InviterChercheurForm, inviterChercheurSchema } from "../schemas";

/** Chercheurs disponibles (jamais rattachés) à inviter, et suivi des rattachements déjà existants
 * — toujours une sélection parmi des comptes réels, jamais une saisie libre d'identité. */
export function ResearchersPage() {
  const { data: disponibles, isLoading: chargementDisponibles } = useAvailableResearchers();
  const { data: rattachements, isLoading: chargementRattachements } = useMyResearchers();
  const [erreur, setErreur] = useState<string | null>(null);
  const [inviteCible, setInviteCible] = useState<{ id: string; label: string } | null>(null);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Chercheurs"
        description="Inviter un chercheur, suivre les invitations en attente, acceptées ou refusées."
      />
      {erreur ? <p className="text-sm text-destructive">{erreur}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
            <Users className="size-4" />
            Chercheurs disponibles
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {chargementDisponibles ? <CardListSkeleton count={2} /> : null}
          {!chargementDisponibles && disponibles?.length === 0 ? (
            <EmptyState
              icon={Users}
              message="Aucun chercheur disponible à inviter pour l'instant."
            />
          ) : null}
          <div className="grid gap-3 sm:grid-cols-2">
            {disponibles?.map((chercheur) => (
              <div
                key={chercheur.id}
                className="flex items-center justify-between gap-3 rounded-lg border p-3"
              >
                <div className="flex items-center gap-3">
                  <InitialsAvatar nom={chercheur.name ?? chercheur.email} size="sm" />
                  <div>
                    <p className="text-sm font-medium text-brand-blue">
                      {chercheur.name ?? chercheur.email}
                    </p>
                    <p className="text-xs text-brand-grey">{chercheur.email}</p>
                  </div>
                </div>
                <Button
                  size="sm"
                  onClick={() =>
                    setInviteCible({ id: chercheur.id, label: chercheur.name ?? chercheur.email })
                  }
                >
                  Inviter
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
            <UserCheck className="size-4" />
            Mes rattachements
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {chargementRattachements ? <CardListSkeleton count={2} /> : null}
          {!chargementRattachements && rattachements?.length === 0 ? (
            <EmptyState icon={UserCheck} message="Aucune invitation envoyée pour l'instant." />
          ) : null}
          {rattachements?.map((rattachement) => (
            <div key={rattachement.id} className="space-y-2 border-b py-3 text-sm last:border-0">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <InitialsAvatar
                    nom={rattachement.researcher_name ?? rattachement.researcher_email}
                    size="sm"
                  />
                  <div>
                    <p className="font-medium text-brand-blue">
                      {rattachement.researcher_name ?? rattachement.researcher_email}
                    </p>
                    <p className="text-xs text-brand-grey">
                      Invité le {new Date(rattachement.invited_at).toLocaleDateString("fr-FR")}
                    </p>
                  </div>
                </div>
                <Badge variant={variantStatutRattachement(rattachement.status)}>
                  {libelleStatutRattachement(rattachement.status)}
                </Badge>
              </div>
              {rattachement.collaboration_terms ? (
                <p className="rounded-md border-l-4 border-brand-green bg-brand-green-light/40 p-2 text-xs text-brand-blue">
                  {rattachement.collaboration_terms}
                </p>
              ) : null}
            </div>
          ))}
        </CardContent>
      </Card>

      <DialogueInvitation
        cible={inviteCible}
        onClose={() => setInviteCible(null)}
        onError={(message) => setErreur(message)}
      />
    </div>
  );
}

function DialogueInvitation({
  cible,
  onClose,
  onError,
}: {
  cible: { id: string; label: string } | null;
  onClose: () => void;
  onError: (message: string) => void;
}) {
  const inviter = useInviteResearcher();
  const form = useForm<InviterChercheurForm>({
    resolver: zodResolver(inviterChercheurSchema),
    defaultValues: { collaboration_terms: "" },
  });

  function onSubmit(values: InviterChercheurForm) {
    if (!cible) return;
    inviter.mutate(
      { researcher_id: cible.id, collaboration_terms: values.collaboration_terms || null },
      {
        onSuccess: () => {
          form.reset({ collaboration_terms: "" });
          onClose();
        },
        onError: (error) =>
          onError(error instanceof ApiError ? error.message : "Échec de l'invitation."),
      },
    );
  }

  return (
    <Dialog open={cible !== null} onOpenChange={(ouvert) => !ouvert && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Inviter {cible?.label}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <FormField
              control={form.control}
              name="collaboration_terms"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Conditions de collaboration (optionnel)</FormLabel>
                  <FormControl>
                    <Textarea
                      rows={4}
                      placeholder="Ex. Analyse ESG du secteur minier, 3 mois, résultats confidentiels."
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button type="submit" className="w-full" disabled={inviter.isPending}>
              {inviter.isPending ? "Envoi..." : "Envoyer l'invitation"}
            </Button>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
