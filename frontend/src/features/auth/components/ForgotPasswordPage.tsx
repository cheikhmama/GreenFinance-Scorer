import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, MailCheck } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { AuthLayout } from "@/shared/layout/AuthLayout";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { useRequestPasswordReset } from "../api";
import { type ForgotPasswordForm, forgotPasswordFormSchema } from "../schemas";

export function ForgotPasswordPage() {
  const requestReset = useRequestPasswordReset();
  const [sent, setSent] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<ForgotPasswordForm>({
    resolver: zodResolver(forgotPasswordFormSchema),
    defaultValues: { email: "" },
  });

  function onSubmit(values: ForgotPasswordForm) {
    if (requestReset.isPending) return;
    setServerError(null);
    requestReset.mutate(values, {
      onSuccess: () => {
        form.reset();
        setSent(true);
      },
      onError: (error) => {
        setServerError(
          error instanceof ApiError && error.status === 429
            ? "Trop de demandes ont été effectuées. Veuillez patienter avant de réessayer."
            : "La demande n’a pas pu être envoyée. Vérifiez votre connexion et réessayez dans quelques instants.",
        );
      },
    });
  }

  return (
    <AuthLayout
      eyebrow="RETROUVEZ VOTRE ACCÈS"
      title="Mot de passe oublié ?"
      description="Indiquez l’adresse e-mail associée à votre compte pour recevoir un lien de réinitialisation."
    >
      {sent ? (
        <div className="space-y-5">
          <Alert role="status" className="border-brand-green/20 bg-brand-green-light/60">
            <MailCheck aria-hidden="true" className="text-brand-green" />
            <AlertTitle>Consultez votre messagerie</AlertTitle>
            <AlertDescription>
              Si un compte actif correspond à cette adresse, vous recevrez un lien valable 30
              minutes. Pensez à vérifier vos courriers indésirables.
            </AlertDescription>
          </Alert>
          <Button
            type="button"
            variant="outline"
            className="h-11 w-full"
            onClick={() => setSent(false)}
          >
            Utiliser une autre adresse
          </Button>
        </div>
      ) : (
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5" noValidate>
            {serverError ? (
              <Alert variant="destructive">
                <AlertTitle>Demande impossible</AlertTitle>
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
                      autoComplete="email"
                      placeholder="vous@organisation.com"
                      className="h-12 rounded-xl"
                      disabled={requestReset.isPending}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button
              type="submit"
              className="h-12 w-full rounded-xl"
              disabled={requestReset.isPending}
            >
              {requestReset.isPending ? "Envoi en cours…" : "Recevoir le lien"}
            </Button>
          </form>
        </Form>
      )}
      <Link
        to="/login"
        className="mt-6 flex items-center justify-center gap-2 rounded text-sm font-medium text-brand-green underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-4"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Retour à la connexion
      </Link>
    </AuthLayout>
  );
}
