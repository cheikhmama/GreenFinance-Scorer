import { PageShell } from "@/shared/layout/PageShell";
import { ProfileIdentityCard } from "@/shared/profile/ProfileIdentityCard";

export function ProfilePage() {
  return (
    <PageShell title="Profil" description="Vos informations de compte.">
      <ProfileIdentityCard />
    </PageShell>
  );
}
