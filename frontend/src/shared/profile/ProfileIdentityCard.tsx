import { zodResolver } from "@hookform/resolvers/zod";
import { Camera, CalendarDays, KeyRound, Mail, MailCheck, Shield, ShieldCheck, ShieldX, X } from "lucide-react";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import {
  useCurrentUser,
  useDeleteAvatar,
  useUpdateMyProfile,
  useUploadAvatar,
} from "@/features/auth/api";
import { PasswordInput } from "@/features/auth/components/PasswordInput";
import { type ModifierProfilForm, modifierProfilFormSchema } from "@/features/auth/schemas";
import { ApiError } from "@/shared/api/errors";
import { ChangePasswordDialog } from "@/shared/profile/ChangePasswordDialog";
import { UserAvatar } from "@/shared/profile/UserAvatar";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";

const LIBELLES_ROLE: Record<string, string> = {
  ADMIN: "Administrateur",
  ENTERPRISE: "Entreprise",
  AUDITOR: "Auditeur",
  INVESTOR: "Investisseur",
  RESEARCHER: "Chercheur",
  INSTITUTION: "Institution",
};

function AvatarEditor({ nom, avatar }: { nom: string; avatar: string | null }) {
  const uploadAvatar = useUploadAvatar();
  const deleteAvatar = useDeleteAvatar();
  const [erreur, setErreur] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const enCours = uploadAvatar.isPending || deleteAvatar.isPending;

  function choisirFichier(event: React.ChangeEvent<HTMLInputElement>) {
    const fichier = event.target.files?.[0];
    event.target.value = "";
    if (!fichier) return;
    setErreur(null);
    uploadAvatar.mutate(fichier, {
      onError: (error) =>
        setErreur(error instanceof ApiError ? error.message : "Échec de l'envoi de la photo."),
    });
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="group relative">
        <UserAvatar nom={nom} avatar={avatar} className="size-24 text-2xl" />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={enCours}
          aria-label="Changer la photo de profil"
          className="absolute -bottom-1 -right-1 grid size-8 place-items-center rounded-full border-2 border-card bg-brand-navy text-white shadow-sm transition hover:bg-brand-navy/90 disabled:opacity-50"
        >
          <Camera className="size-4" />
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="sr-only"
          onChange={choisirFichier}
        />
      </div>
      {avatar ? (
        <button
          type="button"
          onClick={() =>
            deleteAvatar.mutate(undefined, {
              onError: (error) =>
                setErreur(error instanceof ApiError ? error.message : "Échec de la suppression."),
            })
          }
          disabled={enCours}
          className="flex items-center gap-1 text-xs text-brand-grey hover:text-destructive"
        >
          <X className="size-3" />
          Retirer la photo
        </button>
      ) : null}
      {erreur ? <p className="max-w-40 text-center text-xs text-destructive">{erreur}</p> : null}
    </div>
  );
}

/** Socle commun aux 6 espaces (identité + sécurité). Nom, avatar et e-mail sont modifiables —
 * le rôle reste en lecture seule, contrôlé exclusivement par l'Admin (voir
 * app/auth/schemas.py::ModifierProfilRequest). Un nouvel e-mail exige le mot de passe actuel et
 * n'est appliqué qu'après ouverture du lien envoyé à la nouvelle adresse
 * (app/auth/email_change.py) : jusque-là, l'adresse du compte reste l'ancienne. */
export function ProfileIdentityCard() {
  const { data: user } = useCurrentUser();
  const updateProfile = useUpdateMyProfile();
  const [serverError, setServerError] = useState<string | null>(null);
  const [emailEnAttente, setEmailEnAttente] = useState<string | null>(null);
  const form = useForm<ModifierProfilForm>({
    resolver: zodResolver(modifierProfilFormSchema),
    values: { nom: user?.nom ?? "", email: user?.email ?? "", motDePasseActuel: "" },
  });
  const emailSaisi = form.watch("email");

  if (!user) return null;
  const changeEmail = emailSaisi.trim().toLowerCase() !== user.email;

  function onSubmit(values: ModifierProfilForm) {
    setServerError(null);
    if (changeEmail && !values.motDePasseActuel) {
      form.setError("motDePasseActuel", {
        message: "Saisissez votre mot de passe actuel pour changer d'adresse.",
      });
      return;
    }
    updateProfile.mutate(
      {
        nom: values.nom,
        email: values.email,
        mot_de_passe_actuel: changeEmail ? values.motDePasseActuel : undefined,
      },
      {
        onSuccess: (reponse) => setEmailEnAttente(reponse.email_en_attente ?? null),
        onError: (error) => {
          if (error instanceof ApiError && error.code === "email_deja_utilise") {
            form.setError("email", { message: error.message });
            return;
          }
          if (
            error instanceof ApiError &&
            (error.code === "invalid_credentials" || error.code === "mot_de_passe_requis")
          ) {
            form.setError("motDePasseActuel", { message: error.message });
            return;
          }
          setServerError(error instanceof ApiError ? error.message : "Échec de l'enregistrement.");
        },
      },
    );
  }

  return (
    <Card className="overflow-hidden py-0 shadow-sm">
      <div className="bg-gradient-to-br from-brand-navy to-brand-navy/80 px-6 py-8">
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-end">
          <AvatarEditor nom={user.nom ?? user.email} avatar={user.avatar} />
          <div className="text-center sm:text-left">
            <p className="text-xl font-semibold text-white">{user.nom || user.email}</p>
            <p className="text-sm text-white/80">{user.email}</p>
            <Badge variant="secondary" className="mt-2">
              {LIBELLES_ROLE[user.role] ?? user.role}
            </Badge>
          </div>
        </div>
      </div>

      <CardContent className="space-y-6 pb-6">
        {serverError ? (
          <Alert variant="destructive">
            <AlertTitle>Échec</AlertTitle>
            <AlertDescription>{serverError}</AlertDescription>
          </Alert>
        ) : null}
        {emailEnAttente ? (
          <Alert role="status">
            <MailCheck aria-hidden="true" />
            <AlertTitle>Confirmez votre nouvelle adresse</AlertTitle>
            <AlertDescription>
              Un lien a été envoyé à {emailEnAttente}. Votre adresse actuelle reste celle du compte
              tant que ce lien n'a pas été ouvert.
            </AlertDescription>
          </Alert>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex items-start gap-2 rounded-lg border p-3">
            <CalendarDays className="mt-0.5 size-4 shrink-0 text-brand-grey" />
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Membre depuis
              </p>
              <p className="text-sm font-medium text-brand-blue">
                {new Date(user.date_creation).toLocaleDateString("fr-FR")}
              </p>
            </div>
          </div>
          <div className="flex items-start gap-2 rounded-lg border p-3">
            {user.actif ? (
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-brand-green" />
            ) : (
              <ShieldX className="mt-0.5 size-4 shrink-0 text-destructive" />
            )}
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Statut du compte
              </p>
              <p className="text-sm font-medium text-brand-blue">
                {user.actif ? "Actif" : "Désactivé"}
              </p>
            </div>
          </div>
        </div>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 border-t pt-5" noValidate>
            <div className="flex flex-wrap gap-3">
              <FormField
                control={form.control}
                name="nom"
                render={({ field }) => (
                  <FormItem className="min-w-48 flex-1">
                    <FormLabel className="flex items-center gap-1.5">
                      <Shield className="size-3.5 text-brand-grey" />
                      Nom affiché
                    </FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem className="min-w-48 flex-1">
                    <FormLabel className="flex items-center gap-1.5">
                      <Mail className="size-3.5 text-brand-grey" />
                      Adresse e-mail
                    </FormLabel>
                    <FormControl>
                      <Input type="email" autoComplete="email" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            {changeEmail ? (
              <FormField
                control={form.control}
                name="motDePasseActuel"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="flex items-center gap-1.5">
                      <KeyRound className="size-3.5 text-brand-grey" />
                      Mot de passe actuel
                    </FormLabel>
                    <FormControl>
                      <PasswordInput autoComplete="current-password" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            ) : null}
            <div className="flex justify-center pt-3">
              <Button type="submit" size="lg" disabled={updateProfile.isPending} className="min-w-48">
                {updateProfile.isPending ? "Enregistrement..." : "Enregistrer"}
              </Button>
            </div>
          </form>
        </Form>

        <div className="border-t pt-5">
          <ChangePasswordDialog />
        </div>
      </CardContent>
    </Card>
  );
}
