import { useScrollToHash } from "@/shared/hooks/useScrollToHash";
import { PageHeader } from "@/shared/ui/page-header";
import { AccessRequestsSection } from "./AccessRequestsSection";
import { UsersAwaitingActivationSection } from "./UsersAwaitingActivationSection";
import { UsersSection } from "./UsersSection";

export function AdminUsersPage() {
  useScrollToHash();

  return (
    <div className="space-y-8">
      <PageHeader
        title="Utilisateurs"
        description="Création, désactivation et changement de rôle des comptes non-Administrateur."
      />
      <AccessRequestsSection />
      <UsersAwaitingActivationSection />
      <UsersSection />
    </div>
  );
}
