import { FileText, Upload, X } from "lucide-react";
import { type ComponentProps, type DragEvent, useState } from "react";
import { cn } from "@/shared/ui/cn";

function taille(octets: number) {
  return octets < 1024 * 1024
    ? `${Math.max(1, Math.round(octets / 1024))} Ko`
    : `${(octets / (1024 * 1024)).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Mo`;
}

/** Zone de dépôt d'un fichier unique (lettre de mandat PDF). Remplace le sélecteur natif du
 * navigateur, affiché en anglais et sans retour sur le fichier choisi. Le vrai <input type=file>
 * reste dans la zone (masqué visuellement) : il reçoit l'id et les attributs ARIA de FormControl,
 * donc le libellé du champ, la navigation clavier et les lecteurs d'écran fonctionnent comme
 * avant. `file`/`onFile` portent la valeur, contrôlée par le formulaire. */
export function FileDrop({
  file,
  onFile,
  hint,
  className,
  disabled,
  ...inputProps
}: Omit<ComponentProps<"input">, "type" | "value" | "onChange"> & {
  file: File | undefined;
  onFile: (file: File | undefined) => void;
  hint: string;
}) {
  const [survol, setSurvol] = useState(false);

  function deposer(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setSurvol(false);
    if (!disabled) onFile(event.dataTransfer.files?.[0]);
  }

  return (
    <div className={className}>
      <label
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setSurvol(true);
        }}
        onDragLeave={() => setSurvol(false)}
        onDrop={deposer}
        className={cn(
          "flex cursor-pointer items-center gap-3 rounded-xl border border-dashed bg-muted/30 px-4 py-3 transition",
          "hover:border-primary/60 hover:bg-muted/60 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
          "has-[[aria-invalid=true]]:border-destructive",
          survol && "border-primary bg-secondary/60",
          file && "border-solid border-primary/40 bg-secondary/40",
          disabled && "cursor-not-allowed opacity-60",
        )}
      >
        <input
          {...inputProps}
          type="file"
          disabled={disabled}
          className="sr-only"
          onChange={(event) => {
            const choisi = event.target.files?.[0];
            // Vidé aussitôt : re-choisir le même fichier après « Retirer » redéclenche onChange.
            event.target.value = "";
            onFile(choisi);
          }}
        />
        <span
          className={cn(
            "flex size-10 shrink-0 items-center justify-center rounded-lg",
            file ? "bg-primary text-primary-foreground" : "bg-secondary text-primary",
          )}
          aria-hidden="true"
        >
          {file ? <FileText className="size-5" /> : <Upload className="size-5" />}
        </span>
        <span className="min-w-0 flex-1">
          {file ? (
            <>
              <span className="block truncate text-sm font-medium text-foreground">
                {file.name}
              </span>
              <span className="block text-xs text-muted-foreground">
                {taille(file.size)} · cliquez pour remplacer
              </span>
            </>
          ) : (
            <>
              <span className="block text-sm font-medium text-foreground">
                Déposez le fichier ici ou <span className="text-primary underline">parcourez</span>
              </span>
              <span className="block text-xs text-muted-foreground">{hint}</span>
            </>
          )}
        </span>
      </label>
      {file && !disabled ? (
        <button
          type="button"
          onClick={() => onFile(undefined)}
          className="mt-1.5 inline-flex items-center gap-1 rounded text-xs text-muted-foreground hover:text-destructive focus-visible:outline-2 focus-visible:outline-ring"
        >
          <X className="size-3.5" aria-hidden="true" />
          Retirer le fichier
        </button>
      ) : null}
    </div>
  );
}
