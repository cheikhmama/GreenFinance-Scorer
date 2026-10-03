import { ExternalLink, Info, PauseCircle, RotateCcw } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { nomDuPays } from "@/features/registration/referentiels";
import type { EntrepriseProfil } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { formatMontant } from "@/shared/format/etatPosition";
import { PageShell } from "@/shared/layout/PageShell";
import { ProfileIdentityCard } from "@/shared/profile/ProfileIdentityCard";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { useMyCompanyProfile } from "../api";
import { CompanyRegistrationsCard } from "./CompanyRegistrationsCard";

/** Lecture seule — l'édition de la fiche entreprise reste réservée à l'Administrateur
 * (gouvernance actée en Phase 0). L'entreprise d'abord (sa fiche telle que les investisseurs la
 * voient une fois publiée, puis ses immatriculations), le compte de l'utilisateur ensuite. */
export function ProfilePage() {
  const { data: entreprise, isPending, isError, refetch, isFetching } = useMyCompanyProfile();

  return (
    <PageShell
      title="Profil entreprise"
      description="La fiche de votre entreprise et votre compte utilisateur."
    >
      {isPending ? (
        <div className="grid gap-6 lg:grid-cols-3" aria-busy="true">
          <Skeleton className="h-72 lg:col-span-2" />
          <Skeleton className="h-72" />
        </div>
      ) : null}

      {isError ? (
        <Alert variant="destructive">
          <AlertTitle>Fiche entreprise indisponible</AlertTitle>
          <AlertDescription>
            <p>La fiche n’a pas pu être chargée. Vérifiez votre connexion puis réessayez.</p>
            <Button
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              <RotateCcw aria-hidden="true" />
              Réessayer
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {entreprise && entreprise.status === "SUSPENDED" ? (
        <Alert variant="destructive">
          <PauseCircle aria-hidden="true" />
          <AlertTitle>Entreprise suspendue</AlertTitle>
          <AlertDescription>
            Vous ne pouvez plus soumettre de déclaration ni recevoir de nouveaux investissements.
            Les investisseurs qui vous suivent déjà voient cette suspension. Contactez l’équipe pour
            en connaître la raison.
          </AlertDescription>
        </Alert>
      ) : null}

      {entreprise ? (
        <div className="grid items-start gap-6 lg:grid-cols-3">
          <FicheEntreprise entreprise={entreprise} />
          <CompanyRegistrationsCard entreprise={entreprise} />
        </div>
      ) : null}

      {entreprise ? (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="size-3.5 shrink-0" aria-hidden="true" />
          La fiche et les immatriculations sont tenues par l’administrateur de la plateforme.
          <Link
            to="/contact"
            className="font-medium text-primary underline-offset-2 hover:underline"
          >
            Demander une correction
          </Link>
        </p>
      ) : null}

      <section aria-labelledby="titre-compte" className="space-y-3">
        <h2 id="titre-compte" className="text-lg font-semibold tracking-tight text-foreground">
          Votre compte
        </h2>
        <ProfileIdentityCard />
      </section>
    </PageShell>
  );
}

function statutPublication(entreprise: EntrepriseProfil) {
  if (entreprise.status === "SUSPENDED") {
    return { variant: "destructive" as const, libelle: "Suspendue" };
  }
  if (!entreprise.published_at) return { variant: "secondary" as const, libelle: "Non publiée" };
  return {
    variant: "success" as const,
    libelle: `Publiée le ${new Date(entreprise.published_at).toLocaleDateString("fr-FR")}`,
  };
}

function FicheEntreprise({ entreprise }: { entreprise: EntrepriseProfil }) {
  const statut = statutPublication(entreprise);
  return (
    <Card role="region" aria-label="Fiche entreprise" className="lg:col-span-2">
      <CardHeader>
        <CardTitle className="text-base">Fiche entreprise</CardTitle>
        <CardDescription>Telle que les investisseurs la consultent.</CardDescription>
        <CardAction>
          <Badge variant={statut.variant}>{statut.libelle}</Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex items-center gap-4">
          <CompanyAvatar nom={entreprise.name} logo={entreprise.logo} className="size-14" />
          <div className="min-w-0">
            <p className="truncate text-lg font-semibold text-foreground">{entreprise.name}</p>
            <p className="text-sm text-muted-foreground">
              {entreprise.sector} · {nomDuPays(entreprise.country)}
            </p>
          </div>
        </div>

        {!entreprise.published_at && entreprise.status !== "SUSPENDED" ? (
          <p className="rounded-lg border border-dashed bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
            Pas encore visible des investisseurs : la fiche est publiée avec votre premier score
            officiel.
          </p>
        ) : null}

        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Description
          </p>
          <p className="mt-1 text-sm leading-6 text-foreground">
            {entreprise.description ?? (
              <span className="text-muted-foreground">Non renseignée</span>
            )}
          </p>
        </div>

        <dl className="grid gap-4 border-t pt-4 sm:grid-cols-2">
          <Champ libelle="Site officiel">
            {entreprise.website ? (
              <a
                href={entreprise.website}
                target="_blank"
                rel="noreferrer"
                className="inline-flex max-w-full items-center gap-1 text-primary underline-offset-2 hover:underline"
              >
                <span className="truncate">{entreprise.website.replace(/^https?:\/\//, "")}</span>
                <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
                <span className="sr-only">(nouvel onglet)</span>
              </a>
            ) : (
              <span className="text-muted-foreground">Non renseigné</span>
            )}
          </Champ>
          <Champ libelle="Investissement minimum">
            {entreprise.minimum_investment_amount !== null &&
            entreprise.minimum_investment_currency ? (
              formatMontant(
                entreprise.minimum_investment_amount,
                entreprise.minimum_investment_currency,
              )
            ) : (
              <span className="text-muted-foreground">Aucun minimum</span>
            )}
          </Champ>
        </dl>
      </CardContent>
    </Card>
  );
}

function Champ({ libelle, children }: { libelle: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {libelle}
      </dt>
      <dd className="mt-1 text-sm font-medium text-foreground">{children}</dd>
    </div>
  );
}
