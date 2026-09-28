import { ProfileIdentityCard } from "@/shared/profile/ProfileIdentityCard";
import { PageHeader } from "@/shared/ui/page-header";

export function ProfilePage() {
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Chercheur" title="Profil" description="Vos informations de compte." />
      <ProfileIdentityCard />
    </div>
  );
}
