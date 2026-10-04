import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import type {
  InvestorType,
  ResearchDomain,
  UtilisateurAdmin,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  LIBELLES_DOMAINE_RECHERCHE,
  LIBELLES_TYPE_INVESTISSEUR,
} from "@/shared/format/demandeAcces";
import { libelleRole } from "@/shared/format/role";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { useConfirm } from "@/shared/ui/confirm-dialog";
import { type ColonneTable, DataTable } from "@/shared/ui/data-table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
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
import { useCreateUser, useDeactivateUser, useReactivateUser, useTableUtilisateurs } from "../api";
import {
  type CreerUtilisateurForm,
  creerUtilisateurSchema,
  ROLES_ATTRIBUABLES,
  ROLES_CONSULTABLES,
  Role,
  type RoleAttribuable,
} from "../schemas";

/** Gestion des comptes (Phase 3 §3.3, table de données tâche 5.17) — nom, organisation, e-mail
 * et type dans la table ; état, dates, historique et actions (désactiver, réactiver) dans le
 * tiroir. Le rôle se fixe à la création (voir FormulaireCreation) et n'est plus jamais modifiable
 * ensuite — chaque rôle porte son propre espace et ses propres permissions. `?role=` dans l'URL
 * présélectionne le filtre Rôle (/admin/investisseurs, /admin/chercheurs y mènent). */
export function UsersSection() {
  const [searchParams] = useSearchParams();
  const parametreRole = searchParams.get("role");
  const roleUrl = ROLES_CONSULTABLES.includes(parametreRole as Role)
    ? (parametreRole as Role)
    : null;
  // Le formulaire n'accepte jamais ADMIN : retombe sur le premier rôle attribuable.
  const roleCreationParDefaut = ROLES_ATTRIBUABLES.includes(roleUrl as RoleAttribuable)
    ? (roleUrl as RoleAttribuable)
    : ROLES_ATTRIBUABLES[0];
  const [modaleOuverte, setModaleOuverte] = useState(false);
  const { data, isLoading, isError } = useTableUtilisateurs();
  const [ouvertId, setOuvertId] = useState<string | null>(null);

  const colonnes = useMemo<ColonneTable<UtilisateurAdmin>[]>(
    () => [
      {
        id: "nom",
        entete: "Nom",
        masquable: false,
        valeurTri: (u) => u.name ?? u.email,
        cellule: (u) => (
          <span className="font-semibold text-foreground">
            {u.name ?? <span className="font-normal text-muted-foreground">Sans nom</span>}
          </span>
        ),
      },
      {
        id: "organisation",
        entete: "Organisation",
        valeurTri: (u) => u.organization ?? null,
        cellule: (u) => u.organization ?? <span className="text-muted-foreground">—</span>,
      },
      {
        id: "email",
        entete: "E-mail",
        valeurTri: (u) => u.email,
        cellule: (u) => <span className="font-mono text-[12.5px]">{u.email}</span>,
      },
      {
        id: "type",
        entete: "Type / Domaine",
        valeurTri: (u) => typeDuCompte(u),
        cellule: (u) => <span className="text-muted-foreground">{typeDuCompte(u)}</span>,
      },
    ],
    [],
  );

  const ouvert = data?.find((u) => u.id === ouvertId) ?? null;

  return (
    <section aria-labelledby="titre-utilisateurs" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="titre-utilisateurs" className="text-lg font-semibold text-foreground">
          Comptes
        </h2>
        <Button size="sm" onClick={() => setModaleOuverte(true)}>
          Créer un utilisateur
        </Button>
      </div>
      <Dialog open={modaleOuverte} onOpenChange={setModaleOuverte}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Créer un utilisateur</DialogTitle>
          </DialogHeader>
          <FormulaireCreation
            roleAffiche={roleCreationParDefaut}
            onCreated={() => setModaleOuverte(false)}
          />
        </DialogContent>
      </Dialog>
      <DataTable
        libelle="Comptes utilisateurs"
        lignes={data}
        colonnes={colonnes}
        cle={(u) => u.id}
        rechercheDans={(u) => `${u.name ?? ""} ${u.email} ${u.organization ?? ""}`}
        placeholderRecherche="Nom, e-mail, organisation…"
        filtres={[
          { id: "role", libelle: "Rôle", valeur: (u) => libelleRole(u.role) },
          { id: "etat", libelle: "État", valeur: (u) => (u.active ? "Actif" : "Désactivé") },
        ]}
        filtresInitiaux={roleUrl ? { role: [libelleRole(roleUrl)] } : undefined}
        triInitial={{ colonne: "nom", sens: "asc" }}
        surOuvrir={(u) => setOuvertId(u.id)}
        libelleLigne={(u) => u.name ?? u.email}
        ligneActive={ouvertId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucun compte."
        nomExport="utilisateurs"
        memoire="admin-utilisateurs"
      />
      <UtilisateurTiroir utilisateur={ouvert} surFermer={() => setOuvertId(null)} />
    </section>
  );
}

/** « Fonds d’investissement », « Finance durable »… ; à défaut, le rôle. */
function typeDuCompte(u: UtilisateurAdmin): string {
  const detail = u.profile_detail ?? null;
  if (detail && u.role === "INVESTOR") {
    return LIBELLES_TYPE_INVESTISSEUR[detail as InvestorType] ?? detail;
  }
  if (detail && u.role === "RESEARCHER") {
    return LIBELLES_DOMAINE_RECHERCHE[detail as ResearchDomain] ?? detail;
  }
  return libelleRole(u.role);
}

function dateFr(iso: string | null | undefined): string | null {
  return iso ? new Date(iso).toLocaleDateString("fr-FR") : null;
}

function UtilisateurTiroir({
  utilisateur,
  surFermer,
}: {
  utilisateur: UtilisateurAdmin | null;
  surFermer: () => void;
}) {
  const role = utilisateur?.role ?? Role.AUDITOR;
  const deactivate = useDeactivateUser(role);
  const reactivate = useReactivateUser(role);
  const confirm = useConfirm();
  const [erreur, setErreur] = useState<string | null>(null);

  async function desactiver(u: UtilisateurAdmin) {
    const confirme = await confirm({
      title: "Désactiver ce compte ?",
      description: `${u.email} ne pourra plus se connecter et ses sessions en cours seront immédiatement révoquées. Vous pourrez le réactiver à tout moment.`,
      confirmLabel: "Désactiver",
    });
    if (!confirme) return;
    setErreur(null);
    deactivate.mutate(u.id, {
      onError: (err) =>
        setErreur(err instanceof ApiError ? err.message : "Échec de la désactivation."),
    });
  }

  return (
    <Sheet
      open={utilisateur !== null}
      onOpenChange={(o) => {
        if (!o) {
          setErreur(null);
          surFermer();
        }
      }}
    >
      {utilisateur ? (
        <SheetContent>
          <SheetHeader>
            <SheetTitle>{utilisateur.name ?? utilisateur.email}</SheetTitle>
            <SheetDescription>{utilisateur.email}</SheetDescription>
            <div className="flex flex-wrap gap-1.5">
              <Badge variant="info">{libelleRole(utilisateur.role)}</Badge>
              <Badge variant={utilisateur.active ? "success" : "secondary"}>
                {utilisateur.active ? "Actif" : "Désactivé"}
              </Badge>
              {utilisateur.activated_at ? null : (
                <Badge variant="warning">Activation en attente</Badge>
              )}
            </div>
          </SheetHeader>
          <SheetBody>
            {erreur ? (
              <Alert variant="destructive">
                <AlertDescription>{erreur}</AlertDescription>
              </Alert>
            ) : null}
            <SheetSection titre="Profil">
              <SheetFields
                champs={[
                  { libelle: "Organisation", valeur: utilisateur.organization ?? null },
                  { libelle: "Type / Domaine", valeur: typeDuCompte(utilisateur) },
                  {
                    libelle: "Rôle et droits",
                    valeur: `Espace ${libelleRole(utilisateur.role)} uniquement`,
                  },
                ]}
              />
            </SheetSection>
            <SheetSection titre="Compte">
              <SheetFields
                champs={[
                  { libelle: "Créé le", valeur: dateFr(utilisateur.created_at) },
                  {
                    libelle: "Activé le",
                    valeur: dateFr(utilisateur.activated_at) ?? "Lien d’activation non utilisé",
                  },
                  {
                    libelle: "Changement d’e-mail",
                    valeur: utilisateur.pending_email ? `vers ${utilisateur.pending_email}` : null,
                  },
                ]}
              />
            </SheetSection>
            <SheetSection titre="Historique">
              <Link
                to={`/admin/journal-audit?concerne=${utilisateur.id}`}
                className="text-sm font-semibold"
              >
                Journal d’audit de ce compte
              </Link>
            </SheetSection>
          </SheetBody>
          <SheetFooter>
            {utilisateur.role === "ADMIN" ? (
              <p className="text-sm text-muted-foreground">
                Un compte Administrateur ne se désactive pas ici.
              </p>
            ) : utilisateur.active ? (
              <Button
                size="sm"
                variant="destructive-outline"
                loading={deactivate.isPending}
                onClick={() => desactiver(utilisateur)}
              >
                Désactiver
              </Button>
            ) : (
              <Button
                size="sm"
                variant="outline"
                loading={reactivate.isPending}
                onClick={() => {
                  setErreur(null);
                  reactivate.mutate(utilisateur.id, {
                    onError: (err) =>
                      setErreur(
                        err instanceof ApiError ? err.message : "Échec de la réactivation.",
                      ),
                  });
                }}
              >
                Réactiver
              </Button>
            )}
          </SheetFooter>
        </SheetContent>
      ) : null}
    </Sheet>
  );
}

function FormulaireCreation({
  roleAffiche,
  onCreated,
}: {
  roleAffiche: RoleAttribuable;
  onCreated: () => void;
}) {
  const createUser = useCreateUser();
  const [compteCree, setCompteCree] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<CreerUtilisateurForm>({
    resolver: zodResolver(creerUtilisateurSchema),
    defaultValues: { email: "", role: roleAffiche, company_name: "", sector: "", country: "" },
  });
  const roleSaisi = form.watch("role");

  function onSubmit(values: CreerUtilisateurForm) {
    setServerError(null);
    setCompteCree(null);
    createUser.mutate(values, {
      onSuccess: (utilisateur) => {
        setCompteCree(utilisateur.email);
        form.reset({ email: "", role: roleAffiche, company_name: "", sector: "", country: "" });
      },
      onError: (error) => {
        setServerError(error instanceof ApiError ? error.message : "Échec de la création.");
      },
    });
  }

  if (compteCree) {
    return (
      <div className="space-y-4">
        <Alert>
          <AlertTitle>Compte créé</AlertTitle>
          <AlertDescription>
            Un lien d'activation a été envoyé à <span className="font-semibold">{compteCree}</span>{" "}
            — le compte pourra s'y connecter dès qu'il aura posé son propre mot de passe.
          </AlertDescription>
        </Alert>
        <Button onClick={onCreated}>Fermer</Button>
      </div>
    );
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {serverError ? (
          <Alert variant="destructive">
            <AlertTitle>Création impossible</AlertTitle>
            <AlertDescription>{serverError}</AlertDescription>
          </Alert>
        ) : null}

        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Nouveau compte — e-mail</FormLabel>
              <FormControl>
                <Input type="email" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="role"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Rôle</FormLabel>
              <FormControl>
                <Select {...field}>
                  {ROLES_ATTRIBUABLES.map((role) => (
                    <option key={role} value={role}>
                      {libelleRole(role)}
                    </option>
                  ))}
                </Select>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {roleSaisi === Role.ENTERPRISE ? (
          <div className="grid gap-4 border-t pt-4 sm:grid-cols-3">
            <FormField
              control={form.control}
              name="company_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Nom de l'entreprise</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="sector"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Secteur</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="country"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Pays</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        ) : null}

        <Button type="submit" className="w-full" disabled={createUser.isPending}>
          {createUser.isPending ? "Création..." : "Créer et provisionner"}
        </Button>
      </form>
    </Form>
  );
}
