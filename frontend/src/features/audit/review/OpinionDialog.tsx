import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { ApiError } from "@/shared/api/errors";
import { DECISIONS_AUDIT, libelleDecisionAudit } from "@/shared/format/decisionAudit";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Select } from "@/shared/ui/select";
import { Textarea } from "@/shared/ui/textarea";
import { useSubmitOpinion } from "../api";
import { AuditDecision, type SoumettreAvisForm, soumettreAvisSchema } from "../schemas";

/** Avis de l'Auditeur (tâche 5.6) : quatre valeurs, commentaire exigé hors avis favorable. Une fois
 * rendu, la revue est close et le pré-score devient visible. */
export function OpinionDialog({
  rapportId,
  open,
  onOpenChange,
}: {
  rapportId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const soumettre = useSubmitOpinion(rapportId);
  const form = useForm<SoumettreAvisForm>({
    resolver: zodResolver(soumettreAvisSchema),
    defaultValues: { decision: AuditDecision.FAVORABLE, comment: "" },
  });

  function onSubmit(values: SoumettreAvisForm) {
    soumettre.mutate(
      { decision: values.decision, comment: values.comment?.trim() || null },
      { onSuccess: () => onOpenChange(false) },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Rendre l’avis</DialogTitle>
          <DialogDescription>
            L’avis clôt la revue de ce dossier ; la décision finale revient à l’administrateur.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
            {soumettre.isError ? (
              <Alert variant="destructive">
                <AlertDescription>
                  {soumettre.error instanceof ApiError
                    ? soumettre.error.message
                    : "L’avis n’a pas pu être transmis."}
                </AlertDescription>
              </Alert>
            ) : null}
            <FormField
              control={form.control}
              name="decision"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Décision</FormLabel>
                  <FormControl>
                    <Select {...field}>
                      {DECISIONS_AUDIT.map((decision) => (
                        <option key={decision} value={decision}>
                          {libelleDecisionAudit(decision)}
                        </option>
                      ))}
                    </Select>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="comment"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Commentaire</FormLabel>
                  <FormControl>
                    <Textarea rows={4} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Annuler
              </Button>
              <Button type="submit" disabled={soumettre.isPending}>
                {soumettre.isPending ? "Envoi…" : "Envoyer l’avis"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
