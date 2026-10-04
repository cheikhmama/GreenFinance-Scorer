import { FileDown } from "lucide-react";
import { ProfileIdentityCard } from "@/shared/profile/ProfileIdentityCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { useMyInstitutionProfile } from "../api";

export function ProfilePage() {
  const { data: profil } = useMyInstitutionProfile();

  return (
    <div className="space-y-6">
      <PageHeader title="Profil" description="Vos informations de compte." />
      <ProfileIdentityCard />

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">Export</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3 rounded-lg border p-4">
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-blue-50 text-foreground dark:bg-blue-950/50 dark:text-blue-300">
              <FileDown className="size-5" />
            </span>
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                Exports restants
              </p>
              <p className="text-2xl font-semibold text-foreground">
                {profil ? profil.export_quota : "—"}
              </p>
            </div>
          </div>
          <p className="mt-3 text-sm text-muted-foreground">
            Décompté automatiquement à chaque export d'analyse validée.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
