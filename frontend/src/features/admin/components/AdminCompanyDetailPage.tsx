import { zodResolver } from "@hookform/resolvers/zod";
import { Camera, CheckCircle2, FileText, X } from "lucide-react";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router-dom";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { ApiError } from "@/shared/api/errors";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { useConfirm } from "@/shared/ui/confirm-dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";
import { Textarea } from "@/shared/ui/textarea";
import {
  useCompanyDetail,
  useDeleteCompanyLogo,
  usePublishCompany,
  useReactivateCompany,
  useSuspendCompany,
  useUpdateCompanyProfile,
  useUploadCompanyLogo,
  useValidateReport,
} from "../api";
import { DEVISES, type ModifierEntrepriseForm, modifierEntrepriseSchema } from "../schemas";

function LogoEditor({
  entrepriseId,
  nom,
  logo,
}: {
  entrepriseId: string;
  nom: string;
  logo: string | null;
}) {
  const uploadLogo = useUploadCompanyLogo(entrepriseId);
  const deleteLogo = useDeleteCompanyLogo(entrepriseId);
  const confirm = useConfirm();
  const [erreur, setErreur] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const enCours = uploadLogo.isPending || deleteLogo.isPending;

  async function retirerLogo() {
    const confirme = await confirm({
      title: "Retirer le logo ?",
      description: "L'entreprise apparaîtra avec ses initiales à la place, jusqu'à l'envoi d'un nouveau logo.",
      confirmLabel: "Retirer",
      destructive: true,
    });
    if (!confirme) return;
    deleteLogo.mutate(undefined, {
      onError: (error) =>
        setErreur(error instanceof ApiError ? error.message : "Échec de la suppression."),
    });
  }

  function choisirFichier(event: React.ChangeEvent<HTMLInputElement>) {
    const fichier = event.target.files?.[0];
    event.target.value = "";
    if (!fichier) return;
    setErreur(null);
    uploadLogo.mutate(fichier, {
      onError: (error) =>
        setErreur(error instanceof ApiError ? error.message : "Échec de l'envoi du logo."),
    });
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="group relative">
        <CompanyAvatar nom={nom} logo={logo} className="size-24 text-2xl" />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={enCours}
          aria-label="Changer le logo"
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
      {logo ? (
        <button
          type="button"
          onClick={retirerLogo}
          disabled={enCours}
          className="flex items-center gap-1 text-xs text-brand-grey hover:text-destructive"
        >
          <X className="size-3" />
          Retirer le logo
        </button>
      ) : null}
      {erreur ? <p className="max-w-40 text-center text-xs text-destructive">{erreur}</p> : null}
    </div>
  );
}

/** Fiche de détail Admin d'une entreprise — centralise ce que l'Investisseur voit sur sa fiche
 * publiée (logo, nom, secteur, pays, description, site officiel, montant minimum) pour que ces
 * données soient consultées ET modifiées depuis un seul endroit, plutôt que dispersées entre le
 * profil auto-déclaré de l'Entreprise et les seuls logo/montant jusqu'ici gérables ici. */
export function AdminCompanyDetailPage() {
  const { entrepriseId = "" } = useParams<{ entrepriseId: string }>();
  const { data: entreprise, isLoading, isError } = useCompanyDetail(entrepriseId);
  const updateProfile = useUpdateCompanyProfile(entrepriseId);
  const suspend = useSuspendCompany();
  const reactivate = useReactivateCompany();
  const publish = usePublishCompany();
  const validate = useValidateReport(entreprise?.dernier_rapport_id ?? "");
  const confirm = useConfirm();
  const [serverError, setServerError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const form = useForm<ModifierEntrepriseForm>({
    resolver: zodResolver(modifierEntrepriseSchema),
    values: entreprise
      ? {
          nom: entreprise.nom,
          secteur: entreprise.secteur,
          pays: entreprise.pays,
          description: entreprise.description ?? "",
          site_officiel: entreprise.site_officiel ?? "",
          impose_minimum: entreprise.montant_minimum_investissement != null,
          montant_minimum_investissement: entreprise.montant_minimum_investissement ?? undefined,
          devise_montant_minimum: entreprise.devise_montant_minimum ?? DEVISES[0],
        }
      : undefined,
  });
  const imposeMinimum = form.watch("impose_minimum");

  if (isLoading) {
    return (
      <div className="space-y-8">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (isError || !entreprise) return <p className="text-destructive">Entreprise introuvable.</p>;

  const nomEntreprise = entreprise.nom;

  async function suspendre() {
    const confirme = await confirm({
      title: "Suspendre cette entreprise ?",
      description: `${nomEntreprise} ne pourra plus déposer de nouveau rapport tant qu'elle reste suspendue. Vous pourrez la réactiver à tout moment.`,
      confirmLabel: "Suspendre",
    });
    if (!confirme) return;
    setActionError(null);
    suspend.mutate(entrepriseId, {
      onError: (err) => setActionError(err instanceof ApiError ? err.message : "Échec de la suspension."),
    });
  }

  function onSubmit(values: ModifierEntrepriseForm) {
    setServerError(null);
    updateProfile.mutate(
      {
        nom: values.nom,
        secteur: values.secteur,
        pays: values.pays,
        description: values.description || null,
        site_officiel: values.site_officiel || null,
        montant_minimum_investissement: values.impose_minimum
          ? (values.montant_minimum_investissement ?? null)
          : null,
        devise_montant_minimum: values.impose_minimum ? (values.devise_montant_minimum ?? null) : null,
      },
      {
        onError: (error) => {
          setServerError(error instanceof ApiError ? error.message : "Échec de l'enregistrement.");
        },
      },
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title={entreprise.nom}
        description="Profil complet de l'entreprise, tel que présenté à l'Investisseur une fois publiée."
      />
      <Link to="/admin/entreprises" className="text-sm text-brand-green underline underline-offset-2">
        ← Entreprises
      </Link>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-brand-blue">Statut</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
            <LogoEditor entrepriseId={entrepriseId} nom={entreprise.nom} logo={entreprise.logo} />
            <div className="flex flex-col items-center gap-1.5 sm:items-start">
              <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
                <Badge variant={entreprise.actif ? "success" : "destructive"}>
                  {entreprise.actif ? "Active" : "Suspendue"}
                </Badge>
                <Badge variant={entreprise.date_publication ? "success" : "outline"}>
                  {entreprise.date_publication ? "Publiée" : "Non publiée"}
                </Badge>
                <Badge variant={entreprise.utilisateur_id ? "success" : "outline"}>
                  {entreprise.utilisateur_id ? "Compte lié" : "Sans compte"}
                </Badge>
                {entreprise.dernier_statut_rapport ? (
                  <Badge variant={variantStatutRapport(entreprise.dernier_statut_rapport)}>
                    {libelleStatutRapport(entreprise.dernier_statut_rapport)}
                  </Badge>
                ) : (
                  <Badge variant="secondary">Aucun rapport</Badge>
                )}
              </div>
              <Button asChild size="sm" variant="link" className="h-auto p-0">
                <Link to={`/admin/entreprises/${entrepriseId}/rapports`}>
                  {entreprise.nombre_rapports} rapport{entreprise.nombre_rapports > 1 ? "s" : ""} déposé
                  {entreprise.nombre_rapports > 1 ? "s" : ""}
                </Link>
              </Button>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-2 sm:shrink-0 sm:justify-end">
            {entreprise.dernier_rapport_id ? (
              <Button asChild size="sm" variant="outline">
                <Link to={`/admin/rapports/${entreprise.dernier_rapport_id}`}>
                  <FileText className="size-4" />
                  Voir le rapport
                </Link>
              </Button>
            ) : null}
            {entreprise.dernier_statut_rapport === "EN_VALIDATION" && entreprise.dernier_rapport_id ? (
              <Button
                size="sm"
                disabled={validate.isPending}
                onClick={() => {
                  setActionError(null);
                  validate.mutate(
                    { commentaire: null },
                    {
                      onError: (err) =>
                        setActionError(err instanceof ApiError ? err.message : "Échec de la validation."),
                    },
                  );
                }}
              >
                <CheckCircle2 className="size-4" />
                Valider
              </Button>
            ) : null}
            {!entreprise.date_publication ? (
              <Button
                size="sm"
                disabled={publish.isPending}
                onClick={() => {
                  setActionError(null);
                  publish.mutate(entrepriseId, {
                    onError: (err) =>
                      setActionError(err instanceof ApiError ? err.message : "Échec de la publication."),
                  });
                }}
              >
                Publier
              </Button>
            ) : null}
            {entreprise.actif ? (
              <Button size="sm" variant="outline" disabled={suspend.isPending} onClick={suspendre}>
                Suspendre
              </Button>
            ) : (
              <Button
                size="sm"
                variant="outline"
                disabled={reactivate.isPending}
                onClick={() => {
                  setActionError(null);
                  reactivate.mutate(entrepriseId, {
                    onError: (err) =>
                      setActionError(err instanceof ApiError ? err.message : "Échec de la réactivation."),
                  });
                }}
              >
                Réactiver
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
      {actionError ? <p className="text-sm text-destructive">{actionError}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>Profil</CardTitle>
        </CardHeader>
        <CardContent>
          {serverError ? (
            <Alert variant="destructive" className="mb-4">
              <AlertTitle>Échec</AlertTitle>
              <AlertDescription>{serverError}</AlertDescription>
            </Alert>
          ) : null}

          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
              <div className="grid gap-4 sm:grid-cols-3">
                <FormField
                  control={form.control}
                  name="nom"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Nom</FormLabel>
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

              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Textarea rows={3} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="site_officiel"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Site officiel</FormLabel>
                    <FormControl>
                      <Input type="url" placeholder="https://..." {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="space-y-3 border-t pt-4">
                <FormField
                  control={form.control}
                  name="impose_minimum"
                  render={({ field }) => (
                    <FormItem>
                      <label className="flex items-center gap-2 text-sm text-brand-grey">
                        <input
                          type="checkbox"
                          checked={field.value}
                          onChange={(event) => field.onChange(event.target.checked)}
                        />
                        Cette entreprise impose un montant minimum d'investissement
                      </label>
                    </FormItem>
                  )}
                />
                {imposeMinimum ? (
                  <div className="grid gap-4 sm:grid-cols-2">
                    <FormField
                      control={form.control}
                      name="montant_minimum_investissement"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Montant minimum</FormLabel>
                          <FormControl>
                            <Input
                              type="number"
                              step="0.01"
                              min={0}
                              name={field.name}
                              value={field.value ?? ""}
                              onChange={(event) => field.onChange(event.target.valueAsNumber)}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="devise_montant_minimum"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Devise</FormLabel>
                          <FormControl>
                            <Select {...field}>
                              {DEVISES.map((devise) => (
                                <option key={devise} value={devise}>
                                  {devise}
                                </option>
                              ))}
                            </Select>
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                ) : null}
              </div>

              <Button type="submit" disabled={updateProfile.isPending}>
                {updateProfile.isPending ? "Enregistrement..." : "Enregistrer"}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
