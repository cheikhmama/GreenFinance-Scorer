import { zodResolver } from "@hookform/resolvers/zod";
import { Search } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select } from "@/shared/ui/select";
import {
  useChangeUserRole,
  useCreateUser,
  useDeactivateUser,
  useReactivateUser,
  useUsersByRole,
} from "../api";
import {
  type CreerUtilisateurForm,
  creerUtilisateurSchema,
  ROLES_ATTRIBUABLES,
  Role,
  type RoleAttribuable,
} from "../schemas";

/** Gestion des comptes (Phase 3 §3.3) — création, désactivation/réactivation, changement de rôle
 * contrôlé. Le mot de passe temporaire n'est jamais affiché dans cette interface (aucun compte
 * n'a de moyen de le récupérer autrement qu'à l'écran — voir plan de provisioning par e-mail).
 *
 * Recherche et pagination sont portées par l'API (GET /admin/utilisateurs?recherche=&page=&
 * page_size=) : 3 comptes chargés au départ, "Voir plus" charge 3 comptes de plus depuis la base
 * à chaque clic, jusqu'à épuisement de la liste pour la recherche/rôle en cours. */
export function UsersSection() {
  const [roleAffiche, setRoleAffiche] = useState<RoleAttribuable>(Role.AUDITEUR);
  const [recherche, setRecherche] = useState("");
  const [inclureInactifs, setInclureInactifs] = useState(false);
  const [enAttente, setEnAttente] = useState(false);
  const [modaleOuverte, setModaleOuverte] = useState(false);
  const rechercheDebattue = useDebouncedValue(recherche);
  const {
    data,
    isLoading,
    isError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useUsersByRole(roleAffiche, rechercheDebattue, inclureInactifs, enAttente);
  const deactivate = useDeactivateUser(roleAffiche);
  const reactivate = useReactivateUser(roleAffiche);
  const changeRole = useChangeUserRole(roleAffiche);
  const [actionError, setActionError] = useState<string | null>(null);

  const utilisateurs = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle>Utilisateurs</CardTitle>
          <CardDescription>Un compte Administrateur ne peut pas être créé ici.</CardDescription>
        </div>
        <Button onClick={() => setModaleOuverte(true)}>Créer un utilisateur</Button>
      </CardHeader>
      <CardContent className="space-y-6">
        <Dialog open={modaleOuverte} onOpenChange={setModaleOuverte}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Créer un utilisateur</DialogTitle>
            </DialogHeader>
            <FormulaireCreation roleAffiche={roleAffiche} onCreated={() => setModaleOuverte(false)} />
          </DialogContent>
        </Dialog>

        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-brand-grey">Rôle :</span>
            <Select
              value={roleAffiche}
              onChange={(event) => setRoleAffiche(event.target.value as RoleAttribuable)}
              className="w-48"
            >
              {ROLES_ATTRIBUABLES.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </Select>
            <label htmlFor="utilisateurs-recherche" className="relative min-w-56 flex-1">
              <span className="sr-only">Rechercher un utilisateur par e-mail ou nom</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-brand-grey" />
              <Input
                id="utilisateurs-recherche"
                value={recherche}
                onChange={(event) => setRecherche(event.target.value)}
                placeholder="Rechercher par e-mail ou nom"
                className="pl-9"
              />
            </label>
            <label className="flex items-center gap-2 text-sm text-brand-grey">
              <input
                type="checkbox"
                checked={inclureInactifs}
                onChange={(event) => setInclureInactifs(event.target.checked)}
              />
              Afficher les comptes désactivés
            </label>
            <label className="flex items-center gap-2 text-sm text-brand-grey">
              <input
                type="checkbox"
                checked={enAttente}
                onChange={(event) => setEnAttente(event.target.checked)}
              />
              Mot de passe temporaire non changé
            </label>
          </div>

          {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
          {isError ? <p className="text-destructive">Impossible de charger les comptes.</p> : null}
          {actionError ? <p className="text-sm text-destructive">{actionError}</p> : null}
          {!isLoading && !isError && utilisateurs.length === 0 ? (
            <p className="text-brand-grey">
              {inclureInactifs ? "Aucun compte pour ce rôle." : "Aucun compte actif pour ce rôle."}
            </p>
          ) : null}
          {utilisateurs.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-brand-grey">
                    <th className="py-2 pr-4 font-medium">Compte</th>
                    <th className="py-2 pr-4 font-medium">Historique</th>
                    <th className="py-2 pr-4 font-medium">Changer de rôle</th>
                    <th className="py-2 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {utilisateurs.map((utilisateur) => (
                    <tr key={utilisateur.id} className="border-b last:border-0">
                      <td className="py-3 pr-4">
                        <div className="flex items-center gap-2">
                          <span className="text-brand-blue">{utilisateur.email}</span>
                          {!utilisateur.actif ? (
                            <Badge variant="secondary">désactivé</Badge>
                          ) : null}
                          {utilisateur.doit_changer_mot_de_passe ? (
                            <Badge variant="warning">mot de passe temporaire</Badge>
                          ) : null}
                        </div>
                      </td>
                      <td className="py-3 pr-4">
                        <Link
                          to={`/admin/journal-audit?concerne=${utilisateur.id}`}
                          className="text-brand-green underline underline-offset-2"
                        >
                          Historique
                        </Link>
                      </td>
                      <td className="py-3 pr-4">
                        <Select
                          defaultValue=""
                          className="w-44"
                          onChange={(event) => {
                            const nouveauRole = event.target.value as RoleAttribuable;
                            if (!nouveauRole) return;
                            setActionError(null);
                            changeRole.mutate(
                              { utilisateurId: utilisateur.id, payload: { role: nouveauRole } },
                              {
                                onError: (err) =>
                                  setActionError(
                                    err instanceof ApiError
                                      ? err.message
                                      : "Échec du changement de rôle.",
                                  ),
                              },
                            );
                          }}
                        >
                          <option value="">Changer de rôle…</option>
                          {ROLES_ATTRIBUABLES.filter((role) => role !== roleAffiche).map((role) => (
                            <option key={role} value={role}>
                              {role}
                            </option>
                          ))}
                        </Select>
                      </td>
                      <td className="py-3">
                        {utilisateur.actif ? (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={deactivate.isPending}
                            onClick={() => {
                              setActionError(null);
                              deactivate.mutate(utilisateur.id, {
                                onError: (err) =>
                                  setActionError(
                                    err instanceof ApiError
                                      ? err.message
                                      : "Échec de la désactivation.",
                                  ),
                              });
                            }}
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
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {utilisateurs.length > 0 && hasNextPage ? (
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
  const [motDePasseTemporaire, setMotDePasseTemporaire] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<CreerUtilisateurForm>({
    resolver: zodResolver(creerUtilisateurSchema),
    defaultValues: { email: "", role: roleAffiche, nom_entreprise: "", secteur: "", pays: "" },
  });
  const roleSaisi = form.watch("role");

  function onSubmit(values: CreerUtilisateurForm) {
    setServerError(null);
    setMotDePasseTemporaire(null);
    createUser.mutate(values, {
      onSuccess: (utilisateur) => {
        setMotDePasseTemporaire(utilisateur.mot_de_passe_temporaire);
        form.reset({ email: "", role: roleAffiche, nom_entreprise: "", secteur: "", pays: "" });
      },
      onError: (error) => {
        setServerError(error instanceof ApiError ? error.message : "Échec de la création.");
      },
    });
  }

  if (motDePasseTemporaire) {
    return (
      <div className="space-y-4">
        <Alert>
          <AlertTitle>Compte créé</AlertTitle>
          <AlertDescription>
            Mot de passe temporaire à relayer maintenant, il ne sera plus jamais affiché :{" "}
            <code className="font-mono font-semibold">{motDePasseTemporaire}</code>
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
                      {role}
                    </option>
                  ))}
                </Select>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {roleSaisi === Role.ENTREPRISE ? (
          <div className="grid gap-4 border-t pt-4 sm:grid-cols-3">
            <FormField
              control={form.control}
              name="nom_entreprise"
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
              name="secteur"
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
              name="pays"
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
