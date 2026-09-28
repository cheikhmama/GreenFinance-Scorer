import { FileText, Globe, Info, Wallet } from "lucide-react";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { formatMontant } from "@/shared/format/etatPosition";
import { ProfileIdentityCard } from "@/shared/profile/ProfileIdentityCard";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { useMyCompanyProfile } from "../api";

/** Lecture seule — l'édition de la fiche entreprise reste réservée à l'Administrateur
 * (gouvernance actée en Phase 0). Cette section rend enfin visible, pour l'entreprise
 * elle-même, ce que les investisseurs voient une fois publiée. */
export function ProfilePage() {
  const { data: entreprise, isLoading, isError } = useMyCompanyProfile();

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Entreprise" title="Profil" description="Vos informations de compte." />
      <ProfileIdentityCard />

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-brand-blue">Fiche entreprise</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
          {isError ? (
            <p className="text-destructive">Impossible de charger la fiche entreprise.</p>
          ) : null}
          {entreprise ? (
            <>
              <div className="flex flex-wrap items-center gap-3">
                <CompanyAvatar nom={entreprise.nom} logo={entreprise.logo} className="size-14" />
                <div>
                  <p className="font-semibold text-brand-blue">{entreprise.nom}</p>
                  <p className="text-sm text-brand-grey">
                    {entreprise.secteur} — {entreprise.pays}
                  </p>
                </div>
                <Badge
                  variant={
                    entreprise.date_publication && entreprise.actif
                      ? "success"
                      : entreprise.date_publication && !entreprise.actif
                        ? "destructive"
                        : "secondary"
                  }
                  className="ml-auto"
                >
                  {entreprise.date_publication
                    ? entreprise.actif
                      ? `Publiée le ${new Date(entreprise.date_publication).toLocaleDateString("fr-FR")}`
                      : "Suspendue"
                    : "Non publiée"}
                </Badge>
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <div className="flex items-start gap-2 rounded-lg border p-3">
                  <FileText className="mt-0.5 size-4 shrink-0 text-brand-grey" />
                  <div className="min-w-0">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      Description
                    </p>
                    <p className="text-sm font-medium text-brand-blue">
                      {entreprise.description ?? "Non renseignée"}
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-2 rounded-lg border p-3">
                  <Globe className="mt-0.5 size-4 shrink-0 text-brand-grey" />
                  <div className="min-w-0">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      Site officiel
                    </p>
                    <p className="truncate text-sm font-medium text-brand-blue">
                      {entreprise.site_officiel ?? "Non renseigné"}
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-2 rounded-lg border p-3">
                  <Wallet className="mt-0.5 size-4 shrink-0 text-brand-grey" />
                  <div className="min-w-0">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      Montant minimum
                    </p>
                    <p className="text-sm font-medium text-brand-blue">
                      {entreprise.montant_minimum_investissement !== null &&
                      entreprise.devise_montant_minimum
                        ? formatMontant(
                            entreprise.montant_minimum_investissement,
                            entreprise.devise_montant_minimum,
                          )
                        : "Aucun minimum imposé"}
                    </p>
                  </div>
                </div>
              </div>

              <p className="flex items-center gap-1.5 text-xs text-brand-grey">
                <Info className="size-3.5 shrink-0" />
                Ces informations sont gérées par l'Administrateur. Contactez-le pour toute
                correction.
              </p>
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
