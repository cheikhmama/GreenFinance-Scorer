import { PageHeader } from "@/shared/ui/page-header";
import { UsersSection } from "./UsersSection";

export function AdminUsersPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Utilisateurs"
        description="Création, désactivation et changement de rôle des comptes non-Administrateur."
      />
      <UsersSection />
    </div>
  );
}
