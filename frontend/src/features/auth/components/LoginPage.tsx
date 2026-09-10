import { zodResolver } from "@hookform/resolvers/zod";
import { FlaskConical } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { isPrototypeEnabled } from "@/features/prototype/routes";
import { ApiError } from "@/shared/api/errors";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { useLogin } from "../api";
import { type LoginRequest, loginRequestSchema } from "../schemas";

/**
 * Écran de connexion — seule route publique du module auth. Les tableaux de bord
 * par rôle sont protégés par <RequireRole> (shared/RequireRole.tsx) et redirigent ici
 * en l'absence de session valide ; en cas de succès, on redirige vers /dashboard, qui
 * route ensuite vers l'espace correspondant au rôle de l'utilisateur
 * (shared/DashboardRedirect.tsx).
 */
export function LoginPage() {
  const navigate = useNavigate();
  const login = useLogin();
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<LoginRequest>({
    resolver: zodResolver(loginRequestSchema),
    defaultValues: { email: "", password: "" },
  });

  function onSubmit(values: LoginRequest) {
    setServerError(null);
    login.mutate(values, {
      onSuccess: () => navigate("/dashboard", { replace: true }),
      onError: (error: ApiError) => {
        // 401 invalid_credentials est le seul cas métier attendu du contrat
        // POST /auth/login ; tout autre code (panne réseau, 500) reste un message
        // générique pour ne pas laisser fuiter de détail d'implémentation.
        setServerError(
          error instanceof ApiError && error.code === "invalid_credentials"
            ? "Adresse e-mail ou mot de passe incorrect."
            : "Une erreur inattendue est survenue. Veuillez réessayer.",
        );
      },
    });
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-brand-green-light px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-brand-green">GreenFinance-Scorer</CardTitle>
          <CardDescription>Connectez-vous à votre espace.</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
              {serverError ? (
                <Alert variant="destructive">
                  <AlertTitle>Connexion impossible</AlertTitle>
                  <AlertDescription>{serverError}</AlertDescription>
                </Alert>
              ) : null}

              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>E-mail</FormLabel>
                    <FormControl>
                      <Input type="email" autoComplete="username" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Mot de passe</FormLabel>
                    <FormControl>
                      <Input type="password" autoComplete="current-password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Button type="submit" className="w-full" disabled={login.isPending}>
                {login.isPending ? "Connexion..." : "Se connecter"}
              </Button>
            </form>
          </Form>

          {isPrototypeEnabled ? (
            <div className="mt-6 border-t pt-5">
              <p className="text-center text-xs leading-5 text-muted-foreground">
                Évaluez l’interface sans compte ni backend.
              </p>
              <Button
                type="button"
                variant="outline"
                className="mt-3 w-full"
                onClick={() => navigate("/prototype")}
              >
                <FlaskConical />
                Ouvrir le prototype interactif
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
