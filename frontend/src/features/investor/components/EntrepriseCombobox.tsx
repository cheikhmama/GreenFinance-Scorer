import { ChevronsUpDown } from "lucide-react";
import { type ComponentProps, useState } from "react";
import type { EntreprisePublieePublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { cn } from "@/shared/ui/cn";
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList } from "@/shared/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/ui/popover";
import { usePublishedCompanies } from "../api";

/** Recherche et sélection d'une entreprise publiée, sur le même gabarit que shared/ui/combobox
 * (Popover + cmdk) : le bouton déclencheur reçoit l'id et les attributs ARIA de FormControl, donc
 * le libellé du champ et ses erreurs s'y rattachent ; flèches, Entrée et Échap fonctionnent dans
 * la liste (WCAG 2.1.1). La recherche se fait côté serveur (shouldFilter={false}) : cmdk ne
 * refiltre pas les résultats déjà filtrés par l'API.
 *
 * La liste s'affiche dès l'ouverture, même sans rien taper (les toutes premières entreprises
 * publiées) : exiger une frappe avant de montrer quoi que ce soit donnait l'impression qu'aucune
 * entreprise n'était disponible tant qu'on n'avait pas deviné une recherche qui matche — ici on
 * peut aussi bien parcourir que rechercher. */
export function EntrepriseCombobox({
  onSelect,
  placeholder = "Rechercher une entreprise par nom ou secteur...",
  className,
  ...triggerProps
}: Omit<ComponentProps<"button">, "onSelect"> & {
  onSelect: (entreprise: EntreprisePublieePublic) => void;
  placeholder?: string;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [texte, setTexte] = useState("");
  const [choisie, setChoisie] = useState<EntreprisePublieePublic | null>(null);
  const rechercheDebattue = useDebouncedValue(texte);
  const { data } = usePublishedCompanies({ recherche: rechercheDebattue });
  const resultats = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Popover open={ouvert} onOpenChange={setOuvert}>
      <PopoverTrigger asChild>
        <button
          type="button"
          role="combobox"
          aria-expanded={ouvert}
          aria-haspopup="listbox"
          className={cn(
            "flex h-11 w-full items-center justify-between gap-2 rounded-xl border border-input bg-transparent px-3 text-left text-sm shadow-xs outline-none transition-[color,box-shadow] dark:bg-input/30",
            "focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50",
            "aria-invalid:border-destructive aria-invalid:ring-destructive/20",
            className,
          )}
          {...triggerProps}
        >
          <span className={cn("truncate", !choisie && "text-muted-foreground")}>
            {choisie?.name ?? placeholder}
          </span>
          <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-(--radix-popover-trigger-width) min-w-64 p-0">
        <Command shouldFilter={false}>
          <CommandInput
            value={texte}
            onValueChange={setTexte}
            placeholder="Nom ou secteur…"
            aria-label="Rechercher une entreprise"
          />
          <CommandList aria-label="Résultats de la recherche d'entreprise">
            <CommandEmpty>Aucun résultat.</CommandEmpty>
            {resultats.map((entreprise) => (
              <CommandItem
                key={entreprise.id}
                value={entreprise.id}
                onSelect={() => {
                  setChoisie(entreprise);
                  setOuvert(false);
                  onSelect(entreprise);
                }}
              >
                <CompanyAvatar nom={entreprise.name} logo={entreprise.logo} className="size-7" />
                <span className="font-medium text-foreground">{entreprise.name}</span>
                <span className="text-muted-foreground">{entreprise.sector}</span>
              </CommandItem>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
