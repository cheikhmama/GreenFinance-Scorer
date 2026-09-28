import { KeyRound } from "lucide-react";
import { useState } from "react";
import { ChangePasswordSteps } from "@/shared/profile/ChangePasswordSteps";
import { Button } from "@/shared/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/ui/dialog";

/** Entrée volontaire, depuis Profil — la modale se referme et repart à l'étape 1 à chaque
 * fermeture (annulée ou terminée), jamais un état "à moitié fait" laissé en mémoire. */
export function ChangePasswordDialog() {
  const [ouverte, setOuverte] = useState(false);
  return (
    <Dialog open={ouverte} onOpenChange={setOuverte}>
      <Button variant="outline" onClick={() => setOuverte(true)}>
        <KeyRound className="size-4" aria-hidden="true" />
        Changer le mot de passe
      </Button>
      <DialogContent key={ouverte ? "ouverte" : "fermee"}>
        <DialogHeader>
          <DialogTitle>Changer le mot de passe</DialogTitle>
        </DialogHeader>
        <ChangePasswordSteps
          annulable
          onCancel={() => setOuverte(false)}
          onDone={() => setOuverte(false)}
        />
      </DialogContent>
    </Dialog>
  );
}
