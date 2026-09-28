import { TriangleAlert } from "lucide-react";
import { type ReactNode, createContext, useCallback, useContext, useRef, useState } from "react";
import { Button } from "@/shared/ui/button";
import { cn } from "@/shared/ui/cn";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";

export interface ConfirmOptions {
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Style la popup comme une action irréversible (rouge, bouton de confirmation destructeur) —
   * à activer pour toute suppression ou action qu'on ne peut pas annuler après coup. */
  destructive?: boolean;
}

type ConfirmFn = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmFn | null>(null);

/**
 * Remplace window.confirm() par une popup cohérente avec le design de la plateforme, montée une
 * seule fois à la racine (voir main.tsx). `useConfirm()` renvoie `confirm(options)`, une
 * fonction async qui se comporte comme window.confirm — `if (!(await confirm({...}))) return;`
 * — mais sans jamais quitter le design de l'app. Plus aucun alert()/confirm() natif ne doit être
 * ajouté ailleurs dans la plateforme tant que ce composant est disponible.
 */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  const resolveRef = useRef<((valeur: boolean) => void) | null>(null);

  const confirm = useCallback<ConfirmFn>((opts) => {
    setOptions(opts);
    return new Promise<boolean>((resolve) => {
      resolveRef.current = resolve;
    });
  }, []);

  function repondre(valeur: boolean) {
    resolveRef.current?.(valeur);
    resolveRef.current = null;
    setOptions(null);
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Dialog open={options !== null} onOpenChange={(ouvert) => !ouvert && repondre(false)}>
        {options ? (
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <div className="flex items-start gap-3">
                <span
                  className={cn(
                    "grid size-10 shrink-0 place-items-center rounded-full",
                    options.destructive
                      ? "bg-destructive/10 text-destructive"
                      : "bg-brand-green-light text-brand-green",
                  )}
                  aria-hidden="true"
                >
                  <TriangleAlert className="size-5" />
                </span>
                <div className="pt-1.5">
                  <DialogTitle>{options.title}</DialogTitle>
                  <DialogDescription className="mt-1">{options.description}</DialogDescription>
                </div>
              </div>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => repondre(false)}>
                {options.cancelLabel ?? "Annuler"}
              </Button>
              <Button variant={options.destructive ? "destructive" : "default"} onClick={() => repondre(true)}>
                {options.confirmLabel ?? "Confirmer"}
              </Button>
            </DialogFooter>
          </DialogContent>
        ) : null}
      </Dialog>
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): ConfirmFn {
  const context = useContext(ConfirmContext);
  if (!context) {
    throw new Error("useConfirm doit être utilisé à l'intérieur de ConfirmProvider.");
  }
  return context;
}
