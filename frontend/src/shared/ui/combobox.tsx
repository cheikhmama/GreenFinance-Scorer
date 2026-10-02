import { Check, ChevronsUpDown } from "lucide-react";
import { type ComponentProps, useState } from "react";
import { cn } from "@/shared/ui/cn";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/shared/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/ui/popover";

export interface ComboboxOption {
  value: string;
  label: string;
  /** Rubrique d'affichage (ex. « Pays fréquents »), dans l'ordre de première apparition. */
  group?: string;
  /** Autres termes qui retrouvent l'option (ex. le code pays « MR »). */
  keywords?: string[];
}

/** Sans accents ni casse : « energie » retrouve « Énergie », « cote » retrouve « Côte d’Ivoire ». */
function normaliser(texte: string) {
  return texte
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

/** Liste déroulante avec recherche (Popover + cmdk), pour les listes longues. Le bouton
 * déclencheur reçoit l'id et les attributs ARIA de FormControl : le libellé du champ et les
 * messages d'erreur s'y rattachent comme pour un <select>. */
export function Combobox({
  value,
  onValueChange,
  options,
  placeholder = "Choisir…",
  searchPlaceholder = "Rechercher…",
  emptyText = "Aucun résultat.",
  className,
  disabled,
  ...triggerProps
}: Omit<ComponentProps<"button">, "value" | "onChange"> & {
  value: string;
  onValueChange: (value: string) => void;
  options: ComboboxOption[];
  placeholder?: string;
  searchPlaceholder?: string;
  emptyText?: string;
}) {
  const [ouvert, setOuvert] = useState(false);
  const choisie = options.find((option) => option.value === value);
  const groupes = [...new Set(options.map((option) => option.group ?? ""))];

  return (
    <Popover open={ouvert} onOpenChange={setOuvert}>
      <PopoverTrigger asChild>
        <button
          type="button"
          role="combobox"
          aria-expanded={ouvert}
          aria-haspopup="listbox"
          disabled={disabled}
          className={cn(
            "flex h-11 w-full items-center justify-between gap-2 rounded-xl border border-input bg-transparent px-3 text-left text-sm shadow-xs outline-none transition-[color,box-shadow] dark:bg-input/30",
            "focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50",
            "aria-invalid:border-destructive aria-invalid:ring-destructive/20 disabled:cursor-not-allowed disabled:opacity-50",
            className,
          )}
          {...triggerProps}
        >
          <span className={cn("truncate", !choisie && "text-muted-foreground")}>
            {choisie?.label ?? placeholder}
          </span>
          <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-(--radix-popover-trigger-width) min-w-56 p-0">
        <Command
          filter={(_valeur, recherche, motsCles) =>
            normaliser((motsCles ?? []).join(" ")).includes(normaliser(recherche.trim())) ? 1 : 0
          }
        >
          <CommandInput placeholder={searchPlaceholder} />
          <CommandList>
            <CommandEmpty>{emptyText}</CommandEmpty>
            {groupes.map((groupe) => (
              <CommandGroup key={groupe || "_"} heading={groupe || undefined}>
                {options
                  .filter((option) => (option.group ?? "") === groupe)
                  .map((option) => (
                    <CommandItem
                      key={`${groupe}-${option.value}`}
                      value={`${groupe}-${option.value}`}
                      keywords={[option.label, ...(option.keywords ?? [])]}
                      onSelect={() => {
                        onValueChange(option.value);
                        setOuvert(false);
                      }}
                    >
                      <Check
                        className={cn(
                          "size-4 text-primary",
                          option.value === value ? "opacity-100" : "opacity-0",
                        )}
                        aria-hidden="true"
                      />
                      {option.label}
                    </CommandItem>
                  ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
