import { zodResolver } from "@hookform/resolvers/zod";
import { Search, Users } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { libelleRole } from "@/shared/format/role";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { useConfirm } from "@/shared/ui/confirm-dialog";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/ui/dialog";
import { EmptyState } from "@/shared/ui/empty-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import {
  useCreateUser,
  useDeactivateUser,
  useReactivateUser,
  useUsersByRole,
  useUtilisateursApercuRoles,
} from "../api";
import {
  type CreerUtilisateurForm,
  creerUtilisateurSchema,
  ROLES_ATTRIBUABLES,
  ROLES_CONSULTABLES,
  Role,
  type RoleAttribuable,
  type RoleConsultable,
} from "../schemas";

/** Gestion des comptes (Phase 3 §3.3) — création, désactivation/réactivation. Le rôle se fixe à
 * la création (voir FormulaireCreation) et n'est plus jamais modifiable ensuite — chaque rôle
 * porte son propre espace et ses propres permissions, les mélanger après coup n'a pas de sens
 * métier. Le mot de passe temporaire n'est jamais affiché dans cette interface (aucun compte
 * n'a de moyen de le récupérer autrement qu'à l'écran — voir plan de provisioning par e-mail).
 *
 * Recherche et pagination sont portées par l'API (GET /admin/utilisateurs?recherche=&page=&
 * page_size=) : 3 comptes chargés au départ, "Voir plus" charge 3 comptes de plus depuis la base
 * à chaque clic, jusqu'à épuisement de la liste pour la recherche/rôle en cours. Exception : tant
 * que le filtre reste sur sa valeur par défaut ("Tous les rôles") et qu'aucune recherche n'est
 * saisie, cette pagination est remplacée par un repère fixe (un compte par rôle, voir
 * useUtilisateursApercuRoles) — sélectionner un rôle ou chercher un nom revient à la liste
 * paginée habituelle. */
export function UsersSection() {
  const [searchParams, setSearchParams] = useSearchParams();
  const parametreRole = searchParams.get("role");
  // Pas de paramètre, ou valeur invalide (y compris une ancienne valeur "ADMIN" encore dans
  // l'URL/un favori — ce rôle n'est plus une option du filtre) : retombe sur "Tous les rôles".
  const roleAffiche: RoleConsultable | undefined = ROLES_CONSULTABLES.includes(
    parametreRole as RoleConsultable,
  )
    ? (parametreRole as RoleConsultable)
    : undefined;
  // Le formulaire de création n'accepte jamais ADMIN (voir ROLES_ATTRIBUABLES) — depuis "Tous
  // les rôles" ou les comptes Administrateur, retombe sur le premier rôle réellement attribuable
  // plutôt que de présélectionner un rôle que le formulaire refuserait.
  const roleCreationParDefaut =
    roleAffiche && ROLES_ATTRIBUABLES.includes(roleAffiche as RoleAttribuable)
      ? (roleAffiche as RoleAttribuable)
      : ROLES_ATTRIBUABLES[0];
  const [recherche, setRecherche] = useState("");
  const [modaleOuverte, setModaleOuverte] = useState(false);
  const rechercheDebattue = useDebouncedValue(recherche);
  // Entrée sur l'écran, filtre encore à sa valeur par défaut ("Tous les rôles") et aucune
  // recherche en cours : montre un repère (un compte par rôle) plutôt que la liste plate triée
  // par e-mail, qui pourrait ne révéler qu'un seul rôle sur sa première page. Dès qu'un rôle
  // précis est choisi ou qu'une recherche démarre, on repasse sur la liste paginée habituelle.
  const vueParDefaut = roleAffiche === undefined && rechercheDebattue === "";
  const apercuRoles = useUtilisateursApercuRoles(vueParDefaut);
  // Comptes désactivés toujours inclus (jamais de bascule dans l'UI) : sans ça, un compte
  // désactivé disparaîtrait de cette liste et son bouton "Réactiver" deviendrait inatteignable.
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useUsersByRole(roleAffiche, rechercheDebattue, true, false, !vueParDefaut);
  const deactivate = useDeactivateUser();
  const reactivate = useReactivateUser();
  const confirm = useConfirm();
  const [actionError, setActionError] = useState<string | null>(null);

  async function desactiver(utilisateurId: string, email: string) {
    const confirme = await confirm({
      title: "Désactiver ce compte ?",
      description: `${email} ne pourra plus se connecter et ses sessions en cours seront immédiatement révoquées. Vous pourrez le réactiver à tout moment.`,
      confirmLabel: "Désactiver",
    });
    if (!confirme) return;
    setActionError(null);
    deactivate.mutate(utilisateurId, {
      onError: (err) =>
        setActionError(err instanceof ApiError ? err.message : "Échec de la désactivation."),
    });
  }

  const utilisateurs = vueParDefaut
    ? (apercuRoles.data ?? [])
    : (data?.pages.flatMap((page) => page.items) ?? []);
  const chargement = vueParDefaut ? apercuRoles.isLoading : isLoading;
  const erreur = vueParDefaut ? apercuRoles.isError : isError;
  const peutVoirPlus = !vueParDefaut && hasNextPage;

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <CardTitle>Utilisateurs</CardTitle>
        <Button onClick={() => setModaleOuverte(true)}>Créer un utilisateur</Button>
      </CardHeader>
      <CardContent className="space-y-6">
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

        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <label htmlFor="utilisateurs-recherche" className="relative min-w-56 flex-1">
              <span className="sr-only">Rechercher un utilisateur par e-mail ou nom</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="utilisateurs-recherche"
                value={recherche}
                onChange={(event) => setRecherche(event.target.value)}
                placeholder="Rechercher par e-mail ou nom"
                className="pl-9"
              />
            </label>
            <span className="text-sm text-muted-foreground">Rôle :</span>
            <Select
              value={roleAffiche ?? ""}
              onChange={(event) =>
                setSearchParams(
                  (params) => {
                    if (event.target.value) {
                      params.set("role", event.target.value);
                    } else {
                      params.delete("role");
                    }
                    return params;
                  },
                  { replace: true },
                )
              }
              className="w-48"
            >
              <option value="">Tous les rôles</option>
              {ROLES_CONSULTABLES.map((role) => (
                <option key={role} value={role}>
                  {libelleRole(role)}
                </option>
              ))}
            </Select>
          </div>

          {chargement ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : null}
          {erreur ? <p className="text-destructive">Impossible de charger les comptes.</p> : null}
          {actionError ? <p className="text-sm text-destructive">{actionError}</p> : null}
          {!chargement && !erreur && utilisateurs.length === 0 ? (
            <EmptyState
              icon={Users}
              message={roleAffiche ? "Aucun compte pour ce rôle." : "Aucun compte."}
            />
          ) : null}
          {utilisateurs.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Compte</TableHead>
                  <TableHead>Rôle</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead>Historique</TableHead>
                  <TableHead>Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {utilisateurs.map((utilisateur) => (
                  <TableRow key={utilisateur.id}>
                    <TableCell>
                      <div className="min-w-0">
                        {utilisateur.name ? (
                          <p className="font-medium text-foreground">{utilisateur.name}</p>
                        ) : null}
                        <p className="truncate text-sm text-muted-foreground">{utilisateur.email}</p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{libelleRole(utilisateur.role)}</Badge>
                    </TableCell>
                    <TableCell>
                      {utilisateur.active ? (
                        <Badge variant="success">Actif</Badge>
                      ) : (
                        <Badge variant="secondary">Désactivé</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <Button asChild size="sm" variant="outline">
                        <Link to={`/admin/journal-audit?concerne=${utilisateur.id}`}>
                          Historique
                        </Link>
                      </Button>
                    </TableCell>
                    <TableCell>
                      {utilisateur.active ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={deactivate.isPending}
                          onClick={() => desactiver(utilisateur.id, utilisateur.email)}
                        >
                          Désactiver
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={reactivate.isPending}
                          onClick={() => {
                            setActionError(null);
                            reactivate.mutate(utilisateur.id, {
                              onError: (err) =>
                                setActionError(
                                  err instanceof ApiError
                                    ? err.message
                                    : "Échec de la réactivation.",
                                ),
                            });
                          }}
                        >
                          Réactiver
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
          {utilisateurs.length > 0 && peutVoirPlus ? (
            <div>
              <Button
                variant="outline"
                size="sm"
                disabled={isFetchingNextPage}
                onClick={() => fetchNextPage()}
              >
                {isFetchingNextPage ? "Chargement..." : "Voir plus"}
              </Button>
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
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
