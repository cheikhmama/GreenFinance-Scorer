import { useState } from "react";
import type { EntreprisePublieePublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Input } from "@/shared/ui/input";
import { usePublishedCompanies } from "../api";

/** Un seul champ recherche + sélection — jamais une saisie séparée d'un choix dans une liste à
 * côté : taper filtre les résultats affichés juste sous le champ, cliquer un résultat confirme
 * la sélection. Toute frappe après une sélection invalide celle-ci jusqu'au prochain clic.
 *
 * La liste s'affiche dès le focus, même sans rien taper (les toutes premières entreprises
 * publiées) : exiger une frappe avant de montrer quoi que ce soit donnait l'impression qu'aucune
 * entreprise n'était disponible tant qu'on n'avait pas deviné une recherche qui matche — ici on
 * peut aussi bien parcourir que rechercher. */
export function EntrepriseCombobox({
  onSelect,
  placeholder = "Rechercher une entreprise par nom ou secteur...",
}: {
  onSelect: (entreprise: EntreprisePublieePublic) => void;
  placeholder?: string;
}) {
  const [texte, setTexte] = useState("");
  const [ouvert, setOuvert] = useState(false);
  const [confirmee, setConfirmee] = useState(false);
  const rechercheDebattue = useDebouncedValue(texte);
  const { data } = usePublishedCompanies({ recherche: rechercheDebattue });
  const resultats = data?.pages.flatMap((page) => page.items) ?? [];

  function choisir(entreprise: EntreprisePublieePublic) {
    setTexte(entreprise.name);
    setConfirmee(true);
    setOuvert(false);
    onSelect(entreprise);
  }

  return (
    <div className="relative">
      <Input
        value={texte}
        onChange={(event) => {
          setTexte(event.target.value);
          setConfirmee(false);
          setOuvert(true);
        }}
        onFocus={() => setOuvert(true)}
        onBlur={() => setOuvert(false)}
        placeholder={placeholder}
        autoComplete="off"
      />
      {ouvert && !confirmee ? (
        <div
          role="listbox"
          aria-label="Résultats de la recherche d'entreprise"
          className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-md border bg-white shadow-md"
          onMouseDown={(event) => event.preventDefault()}
        >
          {resultats.length === 0 ? (
            <p className="p-3 text-sm text-brand-grey">Aucun résultat.</p>
          ) : (
            resultats.map((entreprise) => (
              <button
                key={entreprise.id}
                type="button"
                role="option"
                aria-selected="false"
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50"
                onClick={() => choisir(entreprise)}
              >
                <CompanyAvatar nom={entreprise.name} logo={entreprise.logo} className="size-7" />
                <span className="font-medium text-brand-blue">{entreprise.name}</span>
                <span className="text-brand-grey">{entreprise.sector}</span>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
