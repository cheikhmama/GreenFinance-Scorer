import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { ApiError } from "@/shared/api/errors";
import type {
  ChercheurDisponible,
  RattachementPublic,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  libelleStatutRattachement,
  variantStatutRattachement,
} from "@/shared/format/statutRattachement";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { type ColonneTable, DataTable } from "@/shared/ui/data-table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { Textarea } from "@/shared/ui/textarea";
import { useAvailableResearchers, useInviteResearcher, useMyResearchers } from "../api";
import { type InviterChercheurForm, inviterChercheurSchema } from "../schemas";

const dateFr = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("fr-FR") : null);
const nomChercheur = (c: { name: string | null; email: string }) => c.name ?? c.email;

/** Rattachements de l'Institution et chercheurs disponibles à inviter (tables de données, tâche
 * 5.18) — toujours une sélection parmi des comptes réels, jamais une saisie libre d'identité.
 * Conditions de collaboration et invitation dans le tiroir. */
export function ResearchersPage() {
  const disponibles = useAvailableResearchers();
  const rattachements = useMyResearchers();
  const [erreur, setErreur] = useState<string | null>(null);
  const [inviteCible, setInviteCible] = useState<{ id: string; label: string } | null>(null);
  const [disponibleId, setDisponibleId] = useState<string | null>(null);
  const [rattachementId, setRattachementId] = useState<string | null>(null);

  const colonnesRattachements = useMemo<ColonneTable<RattachementPublic>[]>(
    () => [
      {
        id: "nom",
        entete: "Chercheur",
        masquable: false,
        valeurTri: (r) => r.researcher_name ?? r.researcher_email,
        cellule: (r) => (
          <span className="flex items-center gap-2.5 font-semibold text-foreground">
            <InitialsAvatar nom={r.researcher_name ?? r.researcher_email} size="sm" />
            {r.researcher_name ?? r.researcher_email}
          </span>
        ),
      },
      {
        id: "email",
        entete: "E-mail",
        valeurTri: (r) => r.researcher_email,
        cellule: (r) => <span className="text-muted-foreground">{r.researcher_email}</span>,
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
  const colonnesDisponibles = useMemo<ColonneTable<ChercheurDisponible>[]>(
    () => [
      {
        id: "nom",
        entete: "Chercheur",
        masquable: false,
        valeurTri: nomChercheur,
        cellule: (c) => (
          <span className="flex items-center gap-2.5 font-semibold text-foreground">
            <InitialsAvatar nom={nomChercheur(c)} size="sm" />
            {nomChercheur(c)}
          </span>
        ),
      },
      {
        id: "email",
        entete: "E-mail",
        valeurTri: (c) => c.email,
        cellule: (c) => <span className="text-muted-foreground">{c.email}</span>,
      },
    ],
    [],
  );

  const rattachement = rattachements.data?.find((r) => r.id === rattachementId) ?? null;
  const disponible = disponibles.data?.find((c) => c.id === disponibleId) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Chercheurs"
        description="Inviter un chercheur, suivre les invitations en attente, acceptées ou refusées."
      />
      {erreur ? (
        <Alert variant="destructive">
          <AlertDescription>{erreur}</AlertDescription>
        </Alert>
      ) : null}

      <Tabs defaultValue="rattachements">
        <TabsList>
          <TabsTrigger value="rattachements">Mes rattachements</TabsTrigger>
          <TabsTrigger value="disponibles">Chercheurs disponibles</TabsTrigger>
        </TabsList>
        <TabsContent value="rattachements">
          <DataTable
            libelle="Mes rattachements"
            lignes={rattachements.data}
            colonnes={colonnesRattachements}
            cle={(r) => r.id}
            rechercheDans={(r) => `${r.researcher_name ?? ""} ${r.researcher_email}`}
            placeholderRecherche="Nom, e-mail…"
            filtres={[
              {
                id: "statut",
                libelle: "Statut",
                valeur: (r) => libelleStatutRattachement(r.status),
              },
            ]}
            triInitial={{ colonne: "invite", sens: "desc" }}
            surOuvrir={(r) => setRattachementId(r.id)}
            libelleLigne={(r) => r.researcher_name ?? r.researcher_email}
            ligneActive={rattachementId}
            chargement={rattachements.isLoading}
            erreur={rattachements.isError}
            messageVide="Aucune invitation envoyée pour l’instant."
            nomExport="rattachements"
            memoire="institution-rattachements"
          />
        </TabsContent>
        <TabsContent value="disponibles">
          <DataTable
            libelle="Chercheurs disponibles"
            lignes={disponibles.data}
            colonnes={colonnesDisponibles}
            cle={(c) => c.id}
            rechercheDans={(c) => `${c.name ?? ""} ${c.email}`}
            placeholderRecherche="Nom, e-mail…"
            triInitial={{ colonne: "nom", sens: "asc" }}
            surOuvrir={(c) => setDisponibleId(c.id)}
            libelleLigne={nomChercheur}
            ligneActive={disponibleId}
            chargement={disponibles.isLoading}
            erreur={disponibles.isError}
            messageVide="Aucun chercheur disponible à inviter pour l’instant."
            nomExport="chercheurs-disponibles"
            memoire="institution-chercheurs-disponibles"
          />
        </TabsContent>
      </Tabs>

      <Sheet open={rattachement !== null} onOpenChange={(o) => !o && setRattachementId(null)}>
        {rattachement ? (
          <SheetContent>
            <SheetHeader>
              <SheetTitle>
                {rattachement.researcher_name ?? rattachement.researcher_email}
              </SheetTitle>
              <SheetDescription>{rattachement.researcher_email}</SheetDescription>
              <Badge variant={variantStatutRattachement(rattachement.status)} className="w-fit">
                {libelleStatutRattachement(rattachement.status)}
              </Badge>
            </SheetHeader>
            <SheetBody>
              <SheetSection titre="Rattachement">
                <SheetFields
                  champs={[
                    { libelle: "Invité le", valeur: dateFr(rattachement.invited_at) },
                    {
                      libelle: "Réponse le",
                      valeur: dateFr(rattachement.responded_at) ?? "En attente de réponse",
                    },
                    { libelle: "Conditions", valeur: rattachement.collaboration_terms },
                  ]}
                />
              </SheetSection>
            </SheetBody>
          </SheetContent>
        ) : null}
      </Sheet>

      <Sheet open={disponible !== null} onOpenChange={(o) => !o && setDisponibleId(null)}>
        {disponible ? (
          <SheetContent>
            <SheetHeader>
              <SheetTitle>{nomChercheur(disponible)}</SheetTitle>
              <SheetDescription>{disponible.email}</SheetDescription>
            </SheetHeader>
            <SheetBody>
              <p className="text-sm text-muted-foreground">
                Ce chercheur n’est rattaché à aucune institution. Invitez-le pour pouvoir l’affecter
                à vos projets.
              </p>
            </SheetBody>
            <SheetFooter>
              <Button
                size="sm"
                onClick={() => {
                  setErreur(null);
                  setInviteCible({ id: disponible.id, label: nomChercheur(disponible) });
                  setDisponibleId(null);
                }}
              >
                Inviter
              </Button>
            </SheetFooter>
          </SheetContent>
        ) : null}
      </Sheet>

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
