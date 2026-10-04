import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { libellePays } from "@/shared/format/pays";
import {
  libelleStatutInscription,
  variantStatutInscription,
} from "@/shared/format/statutInscription";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { usePendingRegistrations } from "../api";
import { KycDialog } from "./KycDialog";

/** Inscriptions qui attendent une décision (tâche 5.11), en tête de la page Entreprises : la
 * plus ancienne d'abord, chacune avec « Examiner », qui ouvre la fenêtre KYC (approuver, demander
 * des informations, refuser). Repliée quand il n'y en a aucune. */
export function PendingRegistrationsSection() {
  const { data: inscriptions, isError } = usePendingRegistrations();
  const [examinee, setExaminee] = useState<string | null>(null);

  if (inscriptions !== undefined && inscriptions.length === 0) return null;

  return (
    <Card id="inscriptions-a-valider">
      <CardHeader>
        <CardTitle className="text-base">
          Inscriptions à valider
          {inscriptions ? (
            <Badge className="ml-2" variant="warning">
              {inscriptions.length}
            </Badge>
          ) : null}
        </CardTitle>
        <CardDescription>
          Entreprises inscrites elles-mêmes, adresse confirmée : vérifiez la demande puis décidez.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isError ? (
          <p className="text-destructive">Impossible de charger les inscriptions.</p>
        ) : null}
        {inscriptions === undefined && !isError ? <CardListSkeleton count={2} /> : null}
        {inscriptions && inscriptions.length > 0 ? (
          <ul aria-label="Inscriptions à valider" className="divide-y">
            {inscriptions.map((inscription) => (
              <li
                key={inscription.company_id}
                className="flex flex-wrap items-center justify-between gap-3 py-3"
              >
                <div className="min-w-0 space-y-0.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      to={`/admin/entreprises/${inscription.company_id}`}
                      className="font-medium text-foreground underline-offset-4 hover:underline"
                    >
                      {inscription.company_name}
                    </Link>
                    <Badge variant={variantStatutInscription(inscription.status)}>
                      {libelleStatutInscription(inscription.status)}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {inscription.sector} · {libellePays(inscription.country)}
                    {inscription.tax_id
                      ? ` · ${inscription.tax_id_type ?? "ID"} ${inscription.tax_id}`
                      : ""}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {inscription.contact_name ?? "—"} · {inscription.contact_email ?? "—"}
                    {inscription.registered_at
                      ? ` · demandée le ${new Date(inscription.registered_at).toLocaleDateString("fr-FR")}`
                      : ""}
                  </p>
                </div>
                <Button size="sm" onClick={() => setExaminee(inscription.company_id)}>
                  <ShieldCheck aria-hidden="true" />
                  Examiner
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
      {examinee ? (
        <KycDialog
          entrepriseId={examinee}
          open
          onOpenChange={(ouvert) => {
            if (!ouvert) setExaminee(null);
          }}
        />
      ) : null}
    </Card>
  );
}
