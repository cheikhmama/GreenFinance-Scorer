import { zodResolver } from "@hookform/resolvers/zod";
import { Camera, CheckCircle2, FileText, Globe, Info, Wallet, X } from "lucide-react";
import type { ReactNode } from "react";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { formatMontant } from "@/shared/format/etatPosition";
import { creerSlug, idDepuisSlug } from "@/shared/format/slug";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import {
  inscriptionEnExamen,
  libelleStatutInscription,
  variantStatutInscription,
} from "@/shared/format/statutInscription";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { useConfirm } from "@/shared/ui/confirm-dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { Skeleton } from "@/shared/ui/skeleton";
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
import { type ModifierEntrepriseForm, modifierEntrepriseSchema } from "../schemas";
import { OnboardingPanel } from "./OnboardingPanel";

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
      description:
        "L'entreprise apparaîtra avec ses initiales à la place, jusqu'à l'envoi d'un nouveau logo.",
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
        <CompanyAvatar nom={nom} logo={logo} className="size-24 text-2xl" decoratif={false} />
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
          // Ouvert par le bouton visible juste au-dessus : hors de l'ordre de tabulation et de
          // l'arbre d'accessibilité, sinon un second arrêt sans nom au clavier.
          tabIndex={-1}
          aria-hidden="true"
          onChange={choisirFichier}
        />
      </div>
      {logo ? (
        <button
          type="button"
          onClick={retirerLogo}
          disabled={enCours}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive"
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
 * publiée (logo, nom, secteur, pays, description, site officiel, montant minimum). L'Admin modifie
 * l'identité (nom, secteur, pays) et le logo ; description, site officiel et montant minimum sont
 * en lecture seule ici, modifiables par l'Entreprise elle-même depuis son propre profil (tâche
 * post-Phase-0, voir frontend/src/features/company/components/ProfilePage.tsx). */
export function AdminCompanyDetailPage() {
  const { entrepriseId: segment = "" } = useParams<{ entrepriseId: string }>();
  const entrepriseId = idDepuisSlug(segment);
  const { data: entreprise, isLoading, isError } = useCompanyDetail(entrepriseId);
  const updateProfile = useUpdateCompanyProfile(entrepriseId);
  const suspend = useSuspendCompany();
  const reactivate = useReactivateCompany();
  const publish = usePublishCompany();
  const validate = useValidateReport(entreprise?.latest_report_id ?? "");
  const confirm = useConfirm();
  const [serverError, setServerError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const form = useForm<ModifierEntrepriseForm>({
    resolver: zodResolver(modifierEntrepriseSchema),
    // `values` n'arrive qu'après le premier rendu : sans valeurs de départ, chaque champ passait
    // de non contrôlé à contrôlé (avertissement React).
    defaultValues: { name: "", sector: "", country: "" },
    values: entreprise
      ? { name: entreprise.name, sector: entreprise.sector, country: entreprise.country }
      : undefined,
  });

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

  const nomEntreprise = entreprise.name;

  async function suspendre() {
    const confirme = await confirm({
      title: "Suspendre cette entreprise ?",
      description: `${nomEntreprise} ne pourra plus déposer de nouveau rapport tant qu'elle reste suspendue. Vous pourrez la réactiver à tout moment.`,
      confirmLabel: "Suspendre",
    });
    if (!confirme) return;
    setActionError(null);
    suspend.mutate(entrepriseId, {
      onError: (err) =>
        setActionError(err instanceof ApiError ? err.message : "Échec de la suspension."),
    });
  }

  function onSubmit(values: ModifierEntrepriseForm) {
    setServerError(null);
    updateProfile.mutate(
      { name: values.name, sector: values.sector, country: values.country },
      {
        onError: (error) => {
          setServerError(error instanceof ApiError ? error.message : "Échec de l'enregistrement.");
        },
      },
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader title={entreprise.name} />
      <Link
        to="/admin/entreprises"
        className="text-sm text-brand-green underline underline-offset-2"
      >
        ← Entreprises
      </Link>

      {inscriptionEnExamen(entreprise.status) ? (
        <OnboardingPanel entrepriseId={entrepriseId} statut={entreprise.status} />
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">Statut</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
            <LogoEditor entrepriseId={entrepriseId} nom={entreprise.name} logo={entreprise.logo} />
            <div className="flex flex-col items-center gap-1.5 sm:items-start">
              <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
                <Badge variant={variantStatutInscription(entreprise.status)}>
                  {libelleStatutInscription(entreprise.status)}
                </Badge>
                <Badge variant={entreprise.published_at ? "success" : "outline"}>
                  {entreprise.published_at ? "Publiée" : "Non publiée"}
                </Badge>
                <Badge variant={entreprise.owner_user_id ? "success" : "outline"}>
                  {entreprise.owner_user_id ? "Compte lié" : "Sans compte"}
                </Badge>
                {entreprise.latest_report_status ? (
                  <Badge variant={variantStatutRapport(entreprise.latest_report_status)}>
                    {libelleStatutRapport(entreprise.latest_report_status)}
                  </Badge>
                ) : (
                  <Badge variant="secondary">Aucun rapport</Badge>
                )}
              </div>
              <Button asChild size="sm" variant="link" className="h-auto p-0">
                <Link to={`/admin/entreprises/${creerSlug(entreprise.name, entrepriseId)}/rapports`}>
                  {entreprise.report_count} rapport{entreprise.report_count > 1 ? "s" : ""} déposé
                  {entreprise.report_count > 1 ? "s" : ""}
                </Link>
              </Button>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-2 sm:shrink-0 sm:justify-end">
            {entreprise.latest_report_id ? (
              <Button asChild size="sm" variant="outline">
                <Link to={`/admin/rapports/${creerSlug(entreprise.name, entreprise.latest_report_id)}`}>
                  <FileText className="size-4" />
                  Voir le rapport
                </Link>
              </Button>
            ) : null}
            {entreprise.latest_report_status === "PENDING_DECISION" &&
            entreprise.latest_report_id ? (
              <Button
                size="sm"
                disabled={validate.isPending}
                onClick={() => {
                  setActionError(null);
                  validate.mutate(
                    { comment: null },
                    {
                      onError: (err) =>
                        setActionError(
                          err instanceof ApiError ? err.message : "Échec de la validation.",
                        ),
                    },
                  );
                }}
              >
                <CheckCircle2 className="size-4" />
                Valider
              </Button>
            ) : null}
            {!entreprise.published_at ? (
              <Button
                size="sm"
                disabled={publish.isPending}
                onClick={() => {
                  setActionError(null);
                  publish.mutate(entrepriseId, {
                    onError: (err) =>
                      setActionError(
                        err instanceof ApiError ? err.message : "Échec de la publication.",
                      ),
                  });
                }}
              >
                Publier
              </Button>
            ) : null}
            {/* Voir EntreprisesTable : jamais d'action de statut sur une inscription en attente. */}
            {entreprise.status === "ACTIVE" ? (
              <Button size="sm" variant="outline" disabled={suspend.isPending} onClick={suspendre}>
                Suspendre
              </Button>
            ) : null}
            {entreprise.status === "SUSPENDED" ? (
              <Button
                size="sm"
                variant="outline"
                disabled={reactivate.isPending}
                onClick={() => {
                  setActionError(null);
                  reactivate.mutate(entrepriseId, {
                    onError: (err) =>
                      setActionError(
                        err instanceof ApiError ? err.message : "Échec de la réactivation.",
                      ),
                  });
                }}
              >
                Réactiver
              </Button>
            ) : null}
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
                  name="name"
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

              <Button type="submit" disabled={updateProfile.isPending}>
                {updateProfile.isPending ? "Enregistrement..." : "Enregistrer"}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Fiche publique</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-3">
          <ChampLectureSeule icone={<FileText />} libelle="Description">
            {entreprise.description ?? "Non renseignée"}
          </ChampLectureSeule>
          <ChampLectureSeule icone={<Globe />} libelle="Site officiel">
            <span className="block truncate">{entreprise.website ?? "Non renseigné"}</span>
          </ChampLectureSeule>
          <ChampLectureSeule icone={<Wallet />} libelle="Montant minimum">
            {entreprise.minimum_investment_amount !== null && entreprise.minimum_investment_currency
              ? formatMontant(
                  entreprise.minimum_investment_amount,
                  entreprise.minimum_investment_currency,
                )
              : "Aucun minimum imposé"}
          </ChampLectureSeule>
          <p className="col-span-full flex items-center gap-1.5 text-xs text-muted-foreground">
            <Info className="size-3.5 shrink-0" aria-hidden="true" />
            Gérée par l'Entreprise elle-même, depuis son propre profil.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function ChampLectureSeule({
  icone,
  libelle,
  children,
}: {
  icone: ReactNode;
  libelle: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-start gap-2 rounded-lg border bg-muted/50 p-3">
      <span className="mt-0.5 shrink-0 text-muted-foreground [&>svg]:size-4" aria-hidden="true">
        {icone}
      </span>
      <div className="min-w-0">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">{libelle}</p>
        <p className="text-sm font-medium text-foreground">{children}</p>
      </div>
    </div>
  );
}
