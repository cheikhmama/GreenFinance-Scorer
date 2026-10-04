import { FileText, Globe, Info, Wallet } from "lucide-react";
import type { ReactNode } from "react";
import type { EntreprisePublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { formatMontant } from "@/shared/format/etatPosition";
import { libellePays } from "@/shared/format/pays";
import { PageShell } from "@/shared/layout/PageShell";
import { ProfileIdentityCard } from "@/shared/profile/ProfileIdentityCard";
import { Badge } from "@/shared/ui/badge";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { useMyCompanyProfile } from "../api";
import { CompanyRegistrationsCard } from "./CompanyRegistrationsCard";

/** Lecture seule — l'édition de la fiche entreprise reste réservée à l'Administrateur
 * (gouvernance actée en Phase 0). Trois sections en cartes : le compte et son contact, la fiche
 * entreprise telle que les investisseurs la voient une fois publiée, puis ses immatriculations
 * (secteur, LEI, ISIN, contrôle GLEIF). */
export function ProfilePage() {
  const { data: entreprise, isPending, isError } = useMyCompanyProfile();

  return (
    <PageShell
      title="Profil entreprise"
      description="Votre compte et la fiche de votre entreprise."
    >
      <ProfileIdentityCard />

      {isPending ? (
        <div className="grid gap-6 lg:grid-cols-3">
          <Skeleton className="h-64 lg:col-span-2" />
          <Skeleton className="h-64" />
        </div>
      ) : null}
      {isError ? (
        <p className="text-sm text-destructive">Impossible de charger la fiche entreprise.</p>
      ) : null}

      {entreprise ? (
        <div className="grid items-start gap-6 lg:grid-cols-3">
          <FicheEntreprise entreprise={entreprise} />
          <CompanyRegistrationsCard entreprise={entreprise} />
        </div>
      ) : null}

      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Info className="size-3.5 shrink-0" aria-hidden="true" />
        Ces informations sont gérées par l'Administrateur. Contactez-le pour toute correction.
      </p>
    </PageShell>
  );
}

function statutPublication(entreprise: EntreprisePublic) {
  if (!entreprise.published_at) return { variant: "secondary" as const, libelle: "Non publiée" };
  if (!entreprise.active) return { variant: "destructive" as const, libelle: "Suspendue" };
  return {
    variant: "success" as const,
    libelle: `Publiée le ${new Date(entreprise.published_at).toLocaleDateString("fr-FR")}`,
  };
}

function FicheEntreprise({ entreprise }: { entreprise: EntreprisePublic }) {
  const statut = statutPublication(entreprise);
  return (
    <Card role="region" aria-label="Fiche entreprise" className="lg:col-span-2">
      <CardHeader>
        <CardTitle className="text-base">Fiche entreprise</CardTitle>
        <CardAction>
          <Badge variant={statut.variant}>{statut.libelle}</Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex items-center gap-3">
          <CompanyAvatar nom={entreprise.name} logo={entreprise.logo} className="size-14" />
          <div className="min-w-0">
            <p className="font-semibold text-foreground">{entreprise.name}</p>
            <p className="text-sm text-muted-foreground">
              {entreprise.sector} — {libellePays(entreprise.country)}
            </p>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <Champ icone={<FileText />} libelle="Description">
            {entreprise.description ?? "Non renseignée"}
          </Champ>
          <Champ icone={<Globe />} libelle="Site officiel">
            <span className="block truncate">{entreprise.website ?? "Non renseigné"}</span>
          </Champ>
          <Champ icone={<Wallet />} libelle="Montant minimum">
            {entreprise.minimum_investment_amount !== null && entreprise.minimum_investment_currency
              ? formatMontant(
                  entreprise.minimum_investment_amount,
                  entreprise.minimum_investment_currency,
                )
              : "Aucun minimum imposé"}
          </Champ>
        </div>
      </CardContent>
    </Card>
  );
}

function Champ({
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
