import {
  CheckCircle2,
  CircleHelp,
  FileText,
  MinusCircle,
  RefreshCw,
  Send,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import { ApiError } from "@/shared/api/errors";
import type {
  KycCheck,
  KycCheckResult,
  KycReport,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  libelleStatutInscription,
  variantStatutInscription,
} from "@/shared/format/statutInscription";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Skeleton } from "@/shared/ui/skeleton";
import { Textarea } from "@/shared/ui/textarea";
import { useCompanyKyc, useOnboardCompany } from "../api";

const RESULTATS: Record<
  KycCheckResult,
  { libelle: string; icone: typeof CheckCircle2; couleur: string }
> = {
  PASSED: { libelle: "Conforme", icone: CheckCircle2, couleur: "text-brand-green" },
  FAILED: { libelle: "Écart", icone: XCircle, couleur: "text-destructive" },
  NOT_VERIFIABLE: { libelle: "Non vérifiable", icone: CircleHelp, couleur: "text-amber-600" },
  NOT_APPLICABLE: { libelle: "Sans objet", icone: MinusCircle, couleur: "text-muted-foreground" },
};

type Action = "approve" | "request_info" | "reject";

function date(valeur: string | null) {
  return valeur ? new Date(valeur).toLocaleDateString("fr-FR") : "—";
}

/** Fenêtre KYC d'une inscription (tâche 5.3) : identité déclarée, contrôles automatiques avec leur
 * source, lettre de mandat, échanges avec le demandeur, et les trois décisions. Les contrôles
 * éclairent la décision, ils ne la prennent pas : aucun écart ne bloque un bouton. */
export function KycDialog({
  entrepriseId,
  open,
  onOpenChange,
}: {
  entrepriseId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const kyc = useCompanyKyc(entrepriseId, open);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Vérification de l’inscription</DialogTitle>
          <DialogDescription>
            Contrôles recalculés à l’ouverture. Ils éclairent votre décision, ils ne la prennent
            pas.
          </DialogDescription>
        </DialogHeader>
        {kyc.isPending ? (
          <div className="space-y-3">
            <Skeleton className="h-6 w-1/2" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : kyc.isError ? (
          <Alert variant="destructive">
            <AlertDescription>Impossible de charger les contrôles. Réessayez.</AlertDescription>
          </Alert>
        ) : (
          <Contenu
            rapport={kyc.data}
            entrepriseId={entrepriseId}
            relancer={() => kyc.refetch()}
            enRelance={kyc.isFetching}
            fermer={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function Contenu({
  rapport,
  entrepriseId,
  relancer,
  enRelance,
  fermer,
}: {
  rapport: KycReport;
  entrepriseId: string;
  relancer: () => void;
  enRelance: boolean;
  fermer: () => void;
}) {
  return (
    <div className="space-y-5">
      <section className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        <Champ libelle="Entreprise" valeur={rapport.company_name} />
        <div>
          <p className="text-xs text-muted-foreground">Statut</p>
          <Badge variant={variantStatutInscription(rapport.status)}>
            {libelleStatutInscription(rapport.status)}
          </Badge>
        </div>
        <Champ libelle="LEI" valeur={rapport.lei ?? "—"} />
        <Champ libelle="ISIN" valeur={rapport.isin ?? "—"} />
        <Champ libelle="Site web" valeur={rapport.website ?? "—"} />
        <Champ libelle="Demande reçue le" valeur={date(rapport.registered_at)} />
        <Champ
          libelle="Contact"
          valeur={[rapport.contact_name, rapport.contact_email].filter(Boolean).join(" — ") || "—"}
        />
        <div>
          <p className="text-xs text-muted-foreground">Lettre de mandat</p>
          {rapport.mandate_letter_available ? (
            <a
              href={`/api/v1/admin/companies/${entrepriseId}/mandate-letter`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 font-medium text-brand-green underline underline-offset-2"
            >
              <FileText className="size-4" aria-hidden="true" />
              Ouvrir (déposée le {date(rapport.mandate_letter_uploaded_at)})
            </a>
          ) : (
            <p className="font-medium text-destructive">Aucune</p>
          )}
        </div>
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">Contrôles automatiques</h3>
          <Button size="sm" variant="ghost" onClick={relancer} disabled={enRelance}>
            <RefreshCw className="size-4" aria-hidden="true" />
            Relancer
          </Button>
        </div>
        <ul className="divide-y rounded-lg border">
          {rapport.checks.map((controle) => (
            <Controle key={controle.code} controle={controle} />
          ))}
        </ul>
      </section>

      {rapport.info_request_message ? (
        <section className="space-y-2 text-sm">
          <h3 className="font-semibold text-foreground">Échanges avec le demandeur</h3>
          <p>
            <span className="text-muted-foreground">
              Informations demandées le {date(rapport.info_requested_at)} :{" "}
            </span>
            <span className="whitespace-pre-line">{rapport.info_request_message}</span>
          </p>
          <p>
            <span className="text-muted-foreground">Réponse : </span>
            {rapport.info_response_message ? (
              <span className="whitespace-pre-line">{rapport.info_response_message}</span>
            ) : rapport.status === "INFO_REQUESTED" ? (
              <span className="italic">en attente</span>
            ) : (
              <span className="italic">nouvelle lettre de mandat, sans message</span>
            )}
          </p>
        </section>
      ) : null}

      <Decisions entrepriseId={entrepriseId} nom={rapport.company_name} fermer={fermer} />
    </div>
  );
}

function Champ({ libelle, valeur }: { libelle: string; valeur: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs text-muted-foreground">{libelle}</p>
      <p className="truncate font-medium text-foreground">{valeur}</p>
    </div>
  );
}

function Controle({ controle }: { controle: KycCheck }) {
  const { libelle, icone: Icone, couleur } = RESULTATS[controle.result];
  return (
    <li className="flex gap-3 p-3 text-sm">
      <Icone className={`mt-0.5 size-5 shrink-0 ${couleur}`} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="font-medium text-foreground">{controle.label}</p>
          <span className={`text-xs font-semibold ${couleur}`}>{libelle}</span>
        </div>
        <p>{controle.detail}</p>
        <p className="text-xs text-muted-foreground">Source : {controle.source}</p>
      </div>
    </li>
  );
}

const TEXTES: Record<
  Exclude<Action, "approve">,
  { libelle: string; bouton: string; champ: "message" | "reason" }
> = {
  request_info: {
    libelle: "Message au demandeur (envoyé par e-mail, visible sur sa page de suivi)",
    bouton: "Envoyer la demande",
    champ: "message",
  },
  reject: {
    libelle: "Motif du refus (envoyé au demandeur)",
    bouton: "Confirmer le refus",
    champ: "reason",
  },
};

function Decisions({
  entrepriseId,
  nom,
  fermer,
}: {
  entrepriseId: string;
  nom: string;
  fermer: () => void;
}) {
  const onboard = useOnboardCompany();
  const [action, setAction] = useState<Action | null>(null);
  const [texte, setTexte] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);

  function choisir(suivante: Action | null) {
    setAction(suivante);
    setTexte("");
    setErreur(null);
  }

  function envoyer() {
    if (action === null) return;
    setErreur(null);
    const corps =
      action === "approve"
        ? { decision: action }
        : { decision: action, [TEXTES[action].champ]: texte.trim() };
    onboard.mutate(
      { entrepriseId, ...corps },
      {
        onSuccess: fermer,
        onError: (error) =>
          setErreur(
            error instanceof ApiError ? error.message : "La décision n’a pas pu être enregistrée.",
          ),
      },
    );
  }

  return (
    <section className="space-y-3 border-t pt-4">
      {erreur ? <p className="text-sm text-destructive">{erreur}</p> : null}
      {action === null ? (
        <DialogFooter>
          <Button variant="outline" onClick={() => choisir("reject")}>
            <XCircle className="size-4" aria-hidden="true" />
            Refuser
          </Button>
          <Button variant="outline" onClick={() => choisir("request_info")}>
            <Send className="size-4" aria-hidden="true" />
            Demander des informations
          </Button>
          <Button onClick={() => choisir("approve")}>
            <CheckCircle2 className="size-4" aria-hidden="true" />
            Approuver
          </Button>
        </DialogFooter>
      ) : action === "approve" ? (
        <div className="space-y-3">
          <p className="text-sm">
            {nom} devient active et son titulaire reçoit un lien, valable 72 heures, pour créer son
            mot de passe.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => choisir(null)} disabled={onboard.isPending}>
              Annuler
            </Button>
            <Button onClick={envoyer} disabled={onboard.isPending}>
              Confirmer l’approbation
            </Button>
          </DialogFooter>
        </div>
      ) : (
        <div className="space-y-2">
          <label htmlFor="texte-decision" className="text-sm font-medium">
            {TEXTES[action].libelle}
          </label>
          <Textarea
            id="texte-decision"
            value={texte}
            maxLength={action === "reject" ? 1000 : 2000}
            onChange={(event) => setTexte(event.target.value)}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => choisir(null)} disabled={onboard.isPending}>
              Annuler
            </Button>
            <Button
              variant={action === "reject" ? "destructive" : "default"}
              onClick={envoyer}
              disabled={onboard.isPending || !texte.trim()}
            >
              {TEXTES[action].bouton}
            </Button>
          </DialogFooter>
        </div>
      )}
    </section>
  );
}
