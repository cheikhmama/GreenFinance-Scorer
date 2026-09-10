import { useSearchParams } from "react-router-dom";
import { PageHeader } from "@/shared/ui/page-header";
import { JournalAuditSection } from "./JournalAuditSection";

export function AdminJournalAuditPage() {
  const [searchParams] = useSearchParams();
  const concerneId = searchParams.get("concerne") ?? undefined;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Journal d'audit"
        description={
          concerneId
            ? "Historique d'activité de ce compte — actions faites ou subies."
            : "Connexions, déconnexions, changements de rôle et désactivations de compte."
        }
      />
      <JournalAuditSection concerneId={concerneId} />
    </div>
  );
}
