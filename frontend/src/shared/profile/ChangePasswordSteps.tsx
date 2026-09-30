import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2, Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import type { ControllerRenderProps } from "react-hook-form";
import { useForm } from "react-hook-form";
import { useChangePassword, useVerifyPassword } from "@/features/auth/api";
import {
  type NouveauMotDePasseForm,
  nouveauMotDePasseFormSchema,
  type VerifierMotDePasseForm,
  verifierMotDePasseFormSchema,
} from "@/features/auth/schemas";
import { ApiError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";

type Etape = "verification" | "nouveau" | "succes";

function ChampMotDePasse({
  field,
  label,
  autoComplete,
}: {
  field: ControllerRenderProps<NouveauMotDePasseForm, "nouveauMotDePasse" | "confirmation">;
  label: string;
  autoComplete: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <FormItem>
      <FormLabel>{label}</FormLabel>
      <FormControl>
        <div className="relative">
          <Input
            type={visible ? "text" : "password"}
            autoComplete={autoComplete}
            className="pr-10"
            {...field}
          />
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            aria-label={visible ? "Masquer le mot de passe" : "Afficher le mot de passe"}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-brand-grey hover:text-brand-blue"
          >
            {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        </div>
      </FormControl>
      <FormMessage />
    </FormItem>
  );
}

/**
 * Parcours progressif — mot de passe actuel → vérification → nouveau mot de passe + confirmation
 * → enregistrement → confirmation de réussite — jamais les 3 champs affichés d'un coup. Contenu
 * seul, sans chrome (page ou modale) : utilisé par ChangePasswordDialog (parcours volontaire
 * depuis Profil, la seule voie d'accès à cette action — rien n'impose plus ce parcours juste
 * après la connexion, voir shared/RequireRole.tsx).
 */
export function ChangePasswordSteps({
  annulable,
  onCancel,
  onDone,
}: {
  annulable: boolean;
  onCancel?: () => void;
  onDone: () => void;
}) {
  const [etape, setEtape] = useState<Etape>("verification");
  const [motDePasseVerifie, setMotDePasseVerifie] = useState("");
  const verifyPassword = useVerifyPassword();
  const changePassword = useChangePassword();

  const verificationForm = useForm<VerifierMotDePasseForm>({
    resolver: zodResolver(verifierMotDePasseFormSchema),
    defaultValues: { motDePasseActuel: "" },
  });

  const nouveauForm = useForm<NouveauMotDePasseForm>({
    resolver: zodResolver(nouveauMotDePasseFormSchema),
    defaultValues: { nouveauMotDePasse: "", confirmation: "" },
  });

  function onVerifier(values: VerifierMotDePasseForm) {
    verifyPassword.mutate(
      { password: values.motDePasseActuel },
      {
        onSuccess: () => {
          setMotDePasseVerifie(values.motDePasseActuel);
          setEtape("nouveau");
        },
        onError: (error) => {
          verificationForm.setError("motDePasseActuel", {
            message:
              error instanceof ApiError && error.code === "invalid_credentials"
                ? "Mot de passe incorrect."
                : "Une erreur inattendue est survenue.",
          });
        },
      },
    );
  }

  function onEnregistrerNouveau(values: NouveauMotDePasseForm) {
    changePassword.mutate(
      { current_password: motDePasseVerifie, new_password: values.nouveauMotDePasse },
      {
        onSuccess: () => setEtape("succes"),
        onError: (error) => {
          nouveauForm.setError("nouveauMotDePasse", {
            message:
              error instanceof ApiError ? error.message : "Une erreur inattendue est survenue.",
          });
        },
      },
    );
  }

  if (etape === "succes") {
    return (
      <div className="flex flex-col items-center gap-3 py-4 text-center">
        <CheckCircle2 className="size-10 text-brand-green" />
        <p className="font-medium text-brand-blue">Mot de passe changé avec succès.</p>
        <Button onClick={onDone} className="w-full">
          Terminer
        </Button>
      </div>
    );
  }

  if (etape === "nouveau") {
    return (
      <Form {...nouveauForm}>
        <form
          onSubmit={nouveauForm.handleSubmit(onEnregistrerNouveau)}
          className="space-y-4"
          noValidate
        >
          <FormField
            control={nouveauForm.control}
            name="nouveauMotDePasse"
            render={({ field }) => (
              <ChampMotDePasse field={field} label="Nouveau mot de passe" autoComplete="new-password" />
            )}
          />
          <FormField
            control={nouveauForm.control}
            name="confirmation"
            render={({ field }) => (
              <ChampMotDePasse
                field={field}
                label="Confirmer le nouveau mot de passe"
                autoComplete="new-password"
              />
            )}
          />
          <Button type="submit" className="w-full" disabled={changePassword.isPending}>
            {changePassword.isPending ? "Enregistrement..." : "Enregistrer"}
          </Button>
          {annulable ? (
            <Button type="button" variant="outline" className="w-full" onClick={onCancel}>
              Annuler
            </Button>
          ) : null}
        </form>
      </Form>
    );
  }

  return (
    <Form {...verificationForm}>
      <form onSubmit={verificationForm.handleSubmit(onVerifier)} className="space-y-4" noValidate>
        <FormField
          control={verificationForm.control}
          name="motDePasseActuel"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Mot de passe actuel</FormLabel>
              <FormControl>
                <Input type="password" autoComplete="current-password" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" className="w-full" disabled={verifyPassword.isPending}>
          {verifyPassword.isPending ? "Vérification..." : "Continuer"}
        </Button>
        {annulable ? (
          <Button type="button" variant="outline" className="w-full" onClick={onCancel}>
            Annuler
          </Button>
        ) : null}
      </form>
    </Form>
  );
}
