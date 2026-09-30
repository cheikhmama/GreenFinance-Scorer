import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, CheckCircle2, LoaderCircle, Send } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { AuthLayout } from "@/shared/layout/AuthLayout";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Textarea } from "@/shared/ui/textarea";
import { useSendContactMessage } from "../api";
import { type ContactForm, contactFormSchema } from "../schemas";

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 429) {
    return "Vous avez envoyé plusieurs demandes récemment. Patientez quelques minutes avant de réessayer.";
  }
  if (error instanceof ApiError && error.status === 503) {
    return "Le service de contact est momentanément indisponible. Votre message n’a pas été envoyé. Réessayez plus tard.";
  }
  return "L’envoi n’a pas pu être confirmé. Vérifiez votre connexion et réessayez. Votre saisie a été conservée.";
}

export function ContactPage() {
  const contact = useSendContactMessage();
  const form = useForm<ContactForm>({
    resolver: zodResolver(contactFormSchema),
    defaultValues: { name: "", email: "", subject: "", message: "" },
  });

  function onSubmit(values: ContactForm) {
    if (!contact.isPending) contact.mutate(values);
  }

  return (
    <AuthLayout
      eyebrow="À votre écoute"
      title="Contactez-nous"
      description="Une question sur votre accès ou sur la plateforme ? Écrivez à notre équipe."
    >
      {contact.isSuccess ? (
        <div className="space-y-6">
          <div
            role="status"
            className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-950"
          >
            <CheckCircle2 aria-hidden="true" className="mb-3 size-8 text-emerald-700" />
            <h2 className="text-lg font-semibold">Votre message a été envoyé</h2>
            <p className="mt-2 break-words text-sm leading-6">
              Merci pour votre demande. Notre équipe pourra vous répondre à l’adresse{" "}
              <span className="font-medium">{contact.variables?.email}</span>.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            className="h-11 w-full rounded-xl"
            onClick={() => {
              form.reset();
              contact.reset();
            }}
          >
            Envoyer un autre message
          </Button>
        </div>
      ) : (
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5" noValidate>
            {contact.isError ? (
              <Alert variant="destructive">
                <AlertTitle>Envoi impossible</AlertTitle>
                <AlertDescription>{getErrorMessage(contact.error)}</AlertDescription>
              </Alert>
            ) : null}

            <fieldset disabled={contact.isPending} className="min-w-0 space-y-4">
              <p className="text-xs text-muted-foreground">Tous les champs sont obligatoires.</p>
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Nom complet</FormLabel>
                      <FormControl>
                        <Input
                          autoComplete="name"
                          maxLength={100}
                          required
                          className="h-11 rounded-xl"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Adresse e-mail</FormLabel>
                      <FormControl>
                        <Input
                          type="email"
                          autoComplete="email"
                          required
                          className="h-11 rounded-xl"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="subject"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Sujet</FormLabel>
                    <FormControl>
                      <Input
                        maxLength={150}
                        placeholder="Ex. : accès à mon espace"
                        required
                        className="h-11 rounded-xl"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="message"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Votre message</FormLabel>
                    <FormControl>
                      <Textarea
                        rows={4}
                        minLength={20}
                        maxLength={5_000}
                        placeholder="Décrivez votre question pour nous aider à vous répondre."
                        required
                        className="min-h-28 resize-y rounded-xl"
                        {...field}
                      />
                    </FormControl>
                    <FormDescription className="text-xs">
                      De 20 à 5 000 caractères. Ne communiquez aucun mot de passe ni document
                      confidentiel.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </fieldset>

            <p className="text-xs leading-5 text-muted-foreground">
              Votre nom, votre adresse e-mail et votre message seront transmis à l’équipe pour
              traiter votre demande.
            </p>
            <Button type="submit" className="h-12 w-full rounded-xl" disabled={contact.isPending}>
              {contact.isPending ? (
                <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
              ) : (
                <Send aria-hidden="true" className="size-4" />
              )}
              {contact.isPending ? "Envoi en cours…" : "Envoyer le message"}
            </Button>
          </form>
        </Form>
      )}

      <div className="mt-6 space-y-4 border-t pt-5 text-center text-sm">
        {!contact.isSuccess ? (
          <p className="text-muted-foreground">
            Mot de passe oublié ?{" "}
            <Link
              to="/mot-de-passe-oublie"
              className="font-medium text-brand-green underline-offset-4 hover:underline"
            >
              Réinitialiser mon accès
            </Link>
          </p>
        ) : null}
        <Link
          to="/login"
          className="inline-flex items-center gap-2 font-medium text-brand-green underline-offset-4 hover:underline"
        >
          <ArrowLeft aria-hidden="true" className="size-4" />
          Retour à la connexion
        </Link>
      </div>
    </AuthLayout>
  );
}
