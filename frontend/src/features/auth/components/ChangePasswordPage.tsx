import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { useChangePassword, useCurrentUser } from "../api";
import { type ChangerMotDePasseForm, changerMotDePasseFormSchema } from "../schemas";

/**
 * Écran de changement de mot de passe obligatoire — POST /auth/changer-mot-de-passe reste
 * accessible même quand doit_changer_mot_de_passe bloque le reste de l'API
 * (app/core/dependencies.py). Sans cet écran, un compte fraîchement provisionné par
 * l'Administrateur (mot de passe temporaire) n'avait aucun moyen de débloquer sa session :
 * RequireRole y redirige désormais tant que doit_changer_mot_de_passe est vrai.
 */
export function ChangePasswordPage() {
  const navigate = useNavigate();
  const { data: user, isLoading, isError } = useCurrentUser();
  const changePassword = useChangePassword();
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<ChangerMotDePasseForm>({
    resolver: zodResolver(changerMotDePasseFormSchema),
    defaultValues: { motDePasseActuel: "", nouveauMotDePasse: "", confirmation: "" },
  });

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-brand-grey">
        Chargement...
      </div>
    );
  }

  if (isError || !user) {
    return <Navigate to="/login" replace />;
  }

  // Rien à faire ici pour un compte déjà à jour — évite une impasse si quelqu'un
  // revient sur cette URL après coup.
  if (!user.doit_changer_mot_de_passe) {
    return <Navigate to="/dashboard" replace />;
  }

  function onSubmit(values: ChangerMotDePasseForm) {
    setServerError(null);
    changePassword.mutate(
      {
        mot_de_passe_actuel: values.motDePasseActuel,
        nouveau_mot_de_passe: values.nouveauMotDePasse,
      },
      {
        onSuccess: () => navigate("/dashboard", { replace: true }),
        onError: (error) => {
          setServerError(
            error instanceof ApiError && error.code === "invalid_credentials"
              ? "Mot de passe actuel incorrect."
              : "Une erreur inattendue est survenue. Veuillez réessayer.",
          );
        },
      },
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-brand-green-light px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-brand-green">Changer le mot de passe</CardTitle>
          <CardDescription>
            Ce compte a été créé avec un mot de passe temporaire. Choisissez-en un nouveau pour
            continuer.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
              {serverError ? (
                <Alert variant="destructive">
                  <AlertTitle>Changement impossible</AlertTitle>
                  <AlertDescription>{serverError}</AlertDescription>
                </Alert>
              ) : null}

              <FormField
                control={form.control}
                name="motDePasseActuel"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Mot de passe temporaire actuel</FormLabel>
                    <FormControl>
                      <Input type="password" autoComplete="current-password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="nouveauMotDePasse"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Nouveau mot de passe</FormLabel>
                    <FormControl>
                      <Input type="password" autoComplete="new-password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="confirmation"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Confirmer le nouveau mot de passe</FormLabel>
                    <FormControl>
                      <Input type="password" autoComplete="new-password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Button type="submit" className="w-full" disabled={changePassword.isPending}>
                {changePassword.isPending ? "Changement..." : "Changer le mot de passe"}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
