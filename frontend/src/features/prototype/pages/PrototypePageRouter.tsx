import { Navigate } from "react-router-dom";
import type { RoleSlug } from "../types";
import { AdminPrototypePage } from "./AdminPrototypePage";
import { AuditPrototypePage } from "./AuditPrototypePage";
import { CompanyPrototypePage } from "./CompanyPrototypePage";
import { InstitutionPrototypePage } from "./InstitutionPrototypePage";
import { InvestorPrototypePage } from "./InvestorPrototypePage";

export function PrototypePageRouter({ role, section }: { role: RoleSlug; section: string }) {
  if (role === "admin") return <AdminPrototypePage section={section} />;
  if (role === "company") return <CompanyPrototypePage section={section} />;
  if (role === "audit") return <AuditPrototypePage section={section} />;
  if (role === "investor") return <InvestorPrototypePage section={section} />;
  // L'espace Chercheur n'a plus de prototype : son backend est réel et complet (Étape 17bis),
  // le sélecteur « Voir comme : Chercheur » renvoie donc directement vers le véritable espace.
  if (role === "researcher") return <Navigate to="/researcher" replace />;
  return <InstitutionPrototypePage section={section} />;
}
