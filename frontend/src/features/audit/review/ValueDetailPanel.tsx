import { Check, PencilLine, SearchX } from "lucide-react";
import { type SyntheticEvent, useEffect, useId, useRef, useState } from "react";
import type {
  MetricReviewEntry,
  ReviewReason,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  libelleMotifRevue,
  libelleStatutRevue,
  MOTIFS_REVUE,
  variantStatutRevue,
} from "@/shared/format/revue";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Select } from "@/shared/ui/select";
import { Textarea } from "@/shared/ui/textarea";
import type { ValeurARevoir } from "./valeurs";

export type ModeRevue = "consulter" | "corriger" | "non_trouvee";

export interface DecisionRevue {
  decision: "ACCEPTED" | "OVERRIDDEN" | "NOT_FOUND";
  new_value?: number;
  reason?: ReviewReason;
  comment?: string;
}

function nombre(valeur: number) {
  return valeur.toLocaleString("fr-FR", { maximumFractionDigits: 6 });
}

function Ligne({ libelle, valeur }: { libelle: string; valeur: string | null }) {
  if (!valeur) return null;
  return (
    <div>
      <dt className="text-xs text-brand-grey">{libelle}</dt>
      <dd className="text-sm text-brand-blue">{valeur}</dd>
    </div>
  );
}

/** Volet de droite de l'espace de revue (tâche 5.7) : la valeur, sa provenance, son historique, et
 * les trois décisions — accepter, corriger (nouvelle valeur + motif), déclarer non trouvée (motif).
 * `modifiable` est faux une fois l'avis rendu : la revue est close (tâche 5.6). */
export function ValueDetailPanel({
  valeur,
  historique,
  mode,
  setMode,
  decider,
  enCours,
  erreur,
  modifiable,
}: {
  valeur: ValeurARevoir;
  historique: MetricReviewEntry[];
  mode: ModeRevue;
  setMode: (mode: ModeRevue) => void;
  decider: (decision: DecisionRevue) => void;
  enCours: boolean;
  erreur: string | null;
  modifiable: boolean;
}) {
  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-brand-grey">
          {valeur.groupe}
        </p>
        <h2 className="break-words text-lg font-semibold text-brand-blue">{valeur.libelle}</h2>
        <div className="mt-2 flex flex-wrap items-baseline gap-2">
          <span className="text-2xl font-semibold text-brand-blue">
            {nombre(valeur.valeurAuditee ?? valeur.valeur)} {valeur.unite}
          </span>
          {valeur.valeurAuditee !== null ? (
            <span className="text-sm text-brand-grey line-through">{nombre(valeur.valeur)}</span>
          ) : null}
          <Badge variant={variantStatutRevue(valeur.statut)}>
            {libelleStatutRevue(valeur.statut)}
          </Badge>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-3">
        <Ligne libelle="Écrit dans le rapport" valeur={valeur.brute} />
        <Ligne libelle="Page" valeur={`p. ${valeur.preuve.page_start}`} />
        <Ligne libelle="Année" valeur={valeur.annee ? String(valeur.annee) : null} />
        <Ligne libelle="Confiance de l’extraction" valeur={valeur.confiance} />
        <Ligne libelle="Rubrique" valeur={valeur.section} />
      </dl>
      {valeur.citation ? (
        <blockquote className="border-l-2 border-brand-green pl-3 text-sm italic text-brand-grey">
          « {valeur.citation} »
        </blockquote>
      ) : null}
      {valeur.boites.length === 0 ? (
        <p className="text-xs text-brand-grey">
          Emplacement non retrouvé sur la page : la page entière fait foi.
        </p>
      ) : null}

      {modifiable ? (
        <Actions
          key={valeur.cle}
          valeur={valeur}
          mode={mode}
          setMode={setMode}
          decider={decider}
          enCours={enCours}
        />
      ) : null}
      {erreur ? <p className="text-sm text-destructive">{erreur}</p> : null}

      {historique.length > 0 ? (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-brand-blue">Historique</h3>
          <ol className="space-y-2 text-sm">
            {[...historique].reverse().map((entree) => (
              <li key={entree.id} className="rounded-md border p-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Badge variant={variantStatutRevue(entree.decision)}>
                    {libelleStatutRevue(entree.decision)}
                  </Badge>
                  <time className="text-xs text-brand-grey">
                    {new Date(entree.created_at).toLocaleString("fr-FR")}
                  </time>
                </div>
                {entree.new_value !== null ? (
                  <p className="mt-1">
                    {nombre(entree.original_value)} → {nombre(entree.new_value)}
                  </p>
                ) : null}
                {entree.reason ? (
                  <p className="text-brand-grey">{libelleMotifRevue(entree.reason)}</p>
                ) : null}
                {entree.comment ? <p className="whitespace-pre-line">{entree.comment}</p> : null}
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </div>
  );
}

function Actions({
  valeur,
  mode,
  setMode,
  decider,
  enCours,
}: {
  valeur: ValeurARevoir;
  mode: ModeRevue;
  setMode: (mode: ModeRevue) => void;
  decider: (decision: DecisionRevue) => void;
  enCours: boolean;
}) {
  const ids = { valeur: useId(), motif: useId(), commentaire: useId() };
  const [nouvelle, setNouvelle] = useState(String(valeur.valeurAuditee ?? valeur.valeur));
  const [motif, setMotif] = useState<ReviewReason>(
    mode === "non_trouvee" ? "NOT_IN_SOURCE" : "EXTRACTION_ERROR",
  );
  const [commentaire, setCommentaire] = useState("");
  const premierChamp = useRef<HTMLInputElement & HTMLSelectElement>(null);

  // Raccourcis E / N : le formulaire s'ouvre avec le premier champ prêt à la saisie.
  useEffect(() => {
    if (mode === "non_trouvee") setMotif("NOT_IN_SOURCE");
    if (mode !== "consulter") premierChamp.current?.focus();
  }, [mode]);

  const nouvelleValeur = Number(nouvelle.replace(",", "."));
  const valeurValide = nouvelle.trim() !== "" && Number.isFinite(nouvelleValeur);

  function soumettre(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mode === "corriger") {
      if (!valeurValide) return;
      decider({
        decision: "OVERRIDDEN",
        new_value: nouvelleValeur,
        reason: motif,
        comment: commentaire.trim() || undefined,
      });
    } else if (mode === "non_trouvee") {
      decider({ decision: "NOT_FOUND", reason: motif, comment: commentaire.trim() || undefined });
    }
  }

  if (mode === "consulter") {
    return (
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => decider({ decision: "ACCEPTED" })} disabled={enCours}>
          <Check className="size-4" aria-hidden="true" />
          Accepter <kbd className="ml-1 rounded border px-1 text-xs">A</kbd>
        </Button>
        <Button variant="outline" onClick={() => setMode("corriger")} disabled={enCours}>
          <PencilLine className="size-4" aria-hidden="true" />
          Corriger <kbd className="ml-1 rounded border px-1 text-xs">E</kbd>
        </Button>
        <Button variant="outline" onClick={() => setMode("non_trouvee")} disabled={enCours}>
          <SearchX className="size-4" aria-hidden="true" />
          Non trouvée <kbd className="ml-1 rounded border px-1 text-xs">N</kbd>
        </Button>
      </div>
    );
  }

  return (
    <form
      onSubmit={soumettre}
      className="space-y-3 rounded-lg border p-3"
      aria-label={mode === "corriger" ? "Corriger la valeur" : "Déclarer la valeur non trouvée"}
    >
      {mode === "corriger" ? (
        <div className="space-y-1">
          <Label htmlFor={ids.valeur}>Valeur corrigée ({valeur.unite})</Label>
          <Input
            id={ids.valeur}
            ref={premierChamp}
            inputMode="decimal"
            value={nouvelle}
            onChange={(event) => setNouvelle(event.target.value)}
            aria-invalid={!valeurValide}
          />
        </div>
      ) : null}
      <div className="space-y-1">
        <Label htmlFor={ids.motif}>Motif</Label>
        <Select
          id={ids.motif}
          ref={mode === "non_trouvee" ? premierChamp : undefined}
          value={motif}
          onChange={(event) => setMotif(event.target.value as ReviewReason)}
        >
          {MOTIFS_REVUE.map((code) => (
            <option key={code} value={code}>
              {libelleMotifRevue(code)}
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1">
        <Label htmlFor={ids.commentaire}>Commentaire (facultatif)</Label>
        <Textarea
          id={ids.commentaire}
          rows={2}
          maxLength={2000}
          value={commentaire}
          onChange={(event) => setCommentaire(event.target.value)}
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={enCours || (mode === "corriger" && !valeurValide)}>
          {mode === "corriger" ? "Enregistrer la correction" : "Confirmer : non trouvée"}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => setMode("consulter")}
          disabled={enCours}
        >
          Annuler
        </Button>
      </div>
    </form>
  );
}
