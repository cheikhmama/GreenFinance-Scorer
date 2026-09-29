import { type SyntheticEvent, useId, useState } from "react";
import { ApiError } from "@/shared/api/errors";
import {
  type CompanyFinancials,
  type CompanyFinancialsRequest,
  DevisePosition,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { auPlusDeuxDecimales, MESSAGE_DEUX_DECIMALES } from "@/shared/format/montant";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Select } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";
import { useCompanyFinancials, useUpdateCompanyFinancials } from "../api";

const DEVISES = Object.values(DevisePosition);

type Valeurs = {
  revenue: string;
  revenue_currency: string;
  enterprise_value: string;
  enterprise_value_currency: string;
  enterprise_value_as_of: string;
};

function depuisServeur(donnees: CompanyFinancials): Valeurs {
  return {
    revenue: donnees.revenue?.toString() ?? "",
    revenue_currency: donnees.revenue_currency ?? DEVISES[0],
    enterprise_value: donnees.enterprise_value?.toString() ?? "",
    enterprise_value_currency: donnees.enterprise_value_currency ?? DEVISES[0],
    enterprise_value_as_of: donnees.enterprise_value_as_of ?? "",
  };
}

/** Montant saisi -> nombre, ou message d'erreur. Vide = donnée absente (null). */
function lireMontant(texte: string): number | null | string {
  if (!texte.trim()) return null;
  const valeur = Number(texte);
  if (!Number.isFinite(valeur) || valeur <= 0) return "Montant strictement positif attendu.";
  if (!auPlusDeuxDecimales(valeur)) return MESSAGE_DEUX_DECIMALES;
  return valeur;
}

/** Chiffre d'affaires et EVIC d'une entreprise (tâche 2.3) : sans eux, le moteur PCAF exclut ses
 * positions (EVIC manquante) ou sa WACI. Remplacement complet — un montant vidé efface la donnée,
 * et sa devise avec elle. */
export function CompanyFinancialsCard({ entrepriseId }: { entrepriseId: string }) {
  const { data, isLoading, isError } = useCompanyFinancials(entrepriseId);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Données financières (PCAF)</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? <Skeleton className="h-24 w-full" /> : null}
        {isError ? (
          <p className="text-destructive">Impossible de charger les données financières.</p>
        ) : null}
        {data ? <FormulaireFinancier entrepriseId={entrepriseId} donnees={data} /> : null}
      </CardContent>
    </Card>
  );
}

function FormulaireFinancier({
  entrepriseId,
  donnees,
}: {
  entrepriseId: string;
  donnees: CompanyFinancials;
}) {
  const mutation = useUpdateCompanyFinancials(entrepriseId);
  const [valeurs, setValeurs] = useState(() => depuisServeur(donnees));
  const [erreurs, setErreurs] = useState<Partial<Record<keyof Valeurs, string>>>({});
  const ids = {
    revenue: useId(),
    revenue_currency: useId(),
    enterprise_value: useId(),
    enterprise_value_currency: useId(),
    enterprise_value_as_of: useId(),
  };

  function changer(champ: keyof Valeurs, valeur: string) {
    setValeurs({ ...valeurs, [champ]: valeur });
  }

  function enregistrer(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mutation.isPending) return;
    const revenue = lireMontant(valeurs.revenue);
    const enterpriseValue = lireMontant(valeurs.enterprise_value);
    const nouvellesErreurs: typeof erreurs = {};
    if (typeof revenue === "string") nouvellesErreurs.revenue = revenue;
    if (typeof enterpriseValue === "string") nouvellesErreurs.enterprise_value = enterpriseValue;
    if (valeurs.enterprise_value_as_of && enterpriseValue === null) {
      nouvellesErreurs.enterprise_value_as_of = "Renseignez l'EVIC avec sa date.";
    }
    setErreurs(nouvellesErreurs);
    if (Object.keys(nouvellesErreurs).length > 0) return;

    const payload: CompanyFinancialsRequest = {
      revenue: revenue as number | null,
      revenue_currency: revenue === null ? null : (valeurs.revenue_currency as DevisePosition),
      enterprise_value: enterpriseValue as number | null,
      enterprise_value_currency:
        enterpriseValue === null ? null : (valeurs.enterprise_value_currency as DevisePosition),
      enterprise_value_as_of: valeurs.enterprise_value_as_of || null,
    };
    mutation.mutate(payload, { onSuccess: (resultat) => setValeurs(depuisServeur(resultat)) });
  }

  const erreurServeur = mutation.error;
  return (
    <form onSubmit={enregistrer} className="space-y-4" noValidate>
      <p className="text-sm text-brand-grey">
        Le chiffre d’affaires sert à la WACI, l’EVIC (valeur d’entreprise trésorerie incluse) au
        facteur d’attribution des émissions financées.
      </p>
      <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
        <ChampMontant
          id={ids.revenue}
          libelle="Chiffre d’affaires"
          valeur={valeurs.revenue}
          erreur={erreurs.revenue}
          onChange={(v) => changer("revenue", v)}
        />
        <ChampDevise
          id={ids.revenue_currency}
          libelle="Devise du chiffre d’affaires"
          valeur={valeurs.revenue_currency}
          onChange={(v) => changer("revenue_currency", v)}
        />
        <ChampMontant
          id={ids.enterprise_value}
          libelle="EVIC"
          valeur={valeurs.enterprise_value}
          erreur={erreurs.enterprise_value}
          onChange={(v) => changer("enterprise_value", v)}
        />
        <ChampDevise
          id={ids.enterprise_value_currency}
          libelle="Devise de l’EVIC"
          valeur={valeurs.enterprise_value_currency}
          onChange={(v) => changer("enterprise_value_currency", v)}
        />
      </div>
      <div className="max-w-xs space-y-1">
        <Label htmlFor={ids.enterprise_value_as_of}>Date de l’EVIC</Label>
        <Input
          id={ids.enterprise_value_as_of}
          type="date"
          value={valeurs.enterprise_value_as_of}
          onChange={(event) => changer("enterprise_value_as_of", event.target.value)}
          aria-invalid={Boolean(erreurs.enterprise_value_as_of)}
        />
        {erreurs.enterprise_value_as_of ? (
          <p className="text-xs text-destructive">{erreurs.enterprise_value_as_of}</p>
        ) : null}
      </div>
      {erreurServeur ? (
        <Alert variant="destructive">
          <AlertDescription>
            {erreurServeur instanceof ApiError
              ? erreurServeur.message
              : "Enregistrement impossible."}
          </AlertDescription>
        </Alert>
      ) : null}
      {mutation.isSuccess ? (
        <p role="status" className="text-sm text-brand-grey">
          Données financières enregistrées.
        </p>
      ) : null}
      <Button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Enregistrement..." : "Enregistrer les données financières"}
      </Button>
    </form>
  );
}

function ChampMontant(props: {
  id: string;
  libelle: string;
  valeur: string;
  erreur?: string;
  onChange: (valeur: string) => void;
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={props.id}>{props.libelle}</Label>
      <Input
        id={props.id}
        type="number"
        min="0"
        step="0.01"
        value={props.valeur}
        onChange={(event) => props.onChange(event.target.value)}
        aria-invalid={Boolean(props.erreur)}
      />
      {props.erreur ? <p className="text-xs text-destructive">{props.erreur}</p> : null}
    </div>
  );
}

function ChampDevise(props: {
  id: string;
  libelle: string;
  valeur: string;
  onChange: (valeur: string) => void;
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={props.id}>{props.libelle}</Label>
      <Select
        id={props.id}
        value={props.valeur}
        onChange={(event) => props.onChange(event.target.value)}
      >
        {DEVISES.map((devise) => (
          <option key={devise} value={devise}>
            {devise}
          </option>
        ))}
      </Select>
    </div>
  );
}
