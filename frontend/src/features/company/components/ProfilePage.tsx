import { Link, Outlet } from "react-router-dom";
import type { EntreprisePublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { libellePays } from "@/shared/format/pays";
import { PageShell } from "@/shared/layout/PageShell";
import { ProfileIdentityCard } from "@/shared/profile/ProfileIdentityCard";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { SheetFields } from "@/shared/ui/sheet";
import { Skeleton } from "@/shared/ui/skeleton";
import { useMyCompanyProfile } from "../api";
import { CompanyRegistrationsCard } from "./CompanyRegistrationsCard";

/** Nom, secteur, pays et logo restent gérés par l'Administrateur (gouvernance Phase 0) ; la
 * description, le site officiel et le montant minimum d'investissement sont modifiables par
 * l'Entreprise elle-même dans le tiroir « Modifier » (tâche post-Phase-0, bascule depuis
 * AdminCompanyDetailPage.tsx). Trois
 * sections en cartes : le compte et son contact, la fiche entreprise telle que les investisseurs
 * la voient une fois publiée, puis ses immatriculations (secteur, LEI, ISIN, contrôle GLEIF). */
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
      <Outlet />
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

/** Résumé en lecture seule de la fiche ; la modification passe par le tiroir routé
 * `fiche-publique` (ProfileEditSheet). */
function FicheEntreprise({ entreprise }: { entreprise: EntreprisePublic }) {
  const statut = statutPublication(entreprise);
  return (
    <Card role="region" aria-label="Fiche entreprise" className="lg:col-span-2">
      <CardHeader>
        <CardTitle className="text-base">Fiche entreprise</CardTitle>
        <CardAction className="flex items-center gap-2">
          <Badge variant={statut.variant}>{statut.libelle}</Badge>
          <Button asChild variant="outline" size="sm">
            <Link to="fiche-publique">Modifier</Link>
          </Button>
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

        <SheetFields
          champs={[
            { libelle: "Description", valeur: entreprise.description },
            { libelle: "Site officiel", valeur: entreprise.website },
            {
              libelle: "Montant minimum",
              valeur:
                entreprise.minimum_investment_amount != null
                  ? `${entreprise.minimum_investment_amount.toLocaleString("fr-FR")} ${entreprise.minimum_investment_currency ?? ""}`
                  : "Aucun",
            },
          ]}
        />
      </CardContent>
    </Card>
  );
}
