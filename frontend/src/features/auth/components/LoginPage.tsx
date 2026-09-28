import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, FlaskConical, LoaderCircle, LockKeyhole } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { isPrototypeEnabled } from "@/features/prototype/routes";
import { ApiError } from "@/shared/api/errors";
import { AuthLayout } from "@/shared/layout/AuthLayout";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { useLogin } from "../api";
import { type LoginRequest, loginRequestSchema } from "../schemas";
import { PasswordInput } from "./PasswordInput";

/**
 * Écran de connexion. Les tableaux de bord
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
    if (login.isPending) return;
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
            : error instanceof ApiError && error.status === 429
              ? "Trop de tentatives de connexion. Veuillez réessayer plus tard."
              : "Une erreur inattendue est survenue. Veuillez réessayer.",
        );
      },
    });
  }

  return (
    <AuthLayout eyebrow="BIENVENUE SUR GREENFINANCE">
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="space-y-5"
          aria-busy={login.isPending}
          noValidate
        >
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
                  <Input
                    type="email"
                    autoComplete="username"
                    placeholder="vous@organisation.fr"
                    spellCheck={false}
                    autoCapitalize="none"
                    readOnly={login.isPending}
                    {...field}
                  />
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
                  <PasswordInput
                    autoComplete="current-password"
                    placeholder="Votre mot de passe"
                    readOnly={login.isPending}
                    {...field}
                  />
                </FormControl>
                <Link
                  to="/mot-de-passe-oublie"
                  className="w-fit text-xs font-medium text-primary underline-offset-4 hover:underline"
                >
                  Mot de passe oublié ?
                </Link>
                <FormMessage />
              </FormItem>
            )}
          />

          <Button type="submit" className="w-full" disabled={login.isPending}>
            {login.isPending ? (
              <LoaderCircle className="motion-safe:animate-spin" aria-hidden="true" />
            ) : null}
            {login.isPending ? "Connexion en cours…" : "Se connecter"}
            {!login.isPending ? <ArrowRight aria-hidden="true" /> : null}
          </Button>
        </form>
      </Form>

      <p className="mt-5 flex items-center justify-center gap-2 text-center text-xs text-muted-foreground">
        <LockKeyhole size={13} aria-hidden="true" />
        Un accès sécurisé à votre espace professionnel
      </p>

      {isPrototypeEnabled ? (
        <div className="mt-6 border-t pt-5">
          <Button
            type="button"
            variant="outline"
            className="h-auto min-h-11 w-full whitespace-normal py-2"
            onClick={() => navigate("/prototype")}
          >
            <FlaskConical aria-hidden="true" />
            Explorer la démonstration
          </Button>
        </div>
      ) : null}
    </AuthLayout>
  );
}
