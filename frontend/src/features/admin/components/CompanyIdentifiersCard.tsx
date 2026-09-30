import { type SyntheticEvent, useId, useState } from "react";
import { ApiError } from "@/shared/api/errors";
import type {
  CompanyIdentifiersRequest,
  EntrepriseAdmin,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { useUpdateCompanyIdentifiers } from "../api";

type Champ = keyof CompanyIdentifiersRequest;

const CHAMPS: { champ: Champ; libelle: string; aide: string }[] = [
  { champ: "isin", libelle: "ISIN", aide: "12 caractères, ex. FR0000120271" },
  { champ: "lei", libelle: "LEI", aide: "20 caractères" },
  { champ: "ticker", libelle: "Ticker", aide: "ex. TTE.PA — peut être partagé entre places" },
];

function valeursInitiales(entreprise: EntrepriseAdmin): Record<Champ, string> {
  return {
    isin: entreprise.isin ?? "",
    lei: entreprise.lei ?? "",
    ticker: entreprise.ticker ?? "",
  };
}

/** Identifiants de marché d'une entreprise (tâche 2.2) : ce sont eux qui rapprochent les lignes
 * d'un import de portefeuille. Formulaire distinct du profil — n'envoie que les champs modifiés,
 * un champ vidé efface l'identifiant (PATCH partiel côté API). */
export function CompanyIdentifiersCard({ entreprise }: { entreprise: EntrepriseAdmin }) {
  const mutation = useUpdateCompanyIdentifiers(entreprise.id);
  // Référence de comparaison tenue en état : remise à jour depuis la réponse du PATCH, sans
  // attendre que la fiche relue redescende en prop.
  const [initiales, setInitiales] = useState(() => valeursInitiales(entreprise));
  const [valeurs, setValeurs] = useState(initiales);
  const ids = { isin: useId(), lei: useId(), ticker: useId() };

  const modifies = CHAMPS.map(({ champ }) => champ).filter(
    (champ) => valeurs[champ].trim() !== initiales[champ],
  );

  function enregistrer(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    if (modifies.length === 0 || mutation.isPending) return;
    const payload: CompanyIdentifiersRequest = {};
    for (const champ of modifies) payload[champ] = valeurs[champ].trim() || null;
    mutation.mutate(payload, {
      onSuccess: (resultat) => {
        const enregistrees = {
          isin: resultat.isin ?? "",
          lei: resultat.lei ?? "",
          ticker: resultat.ticker ?? "",
        };
        setInitiales(enregistrees);
        setValeurs(enregistrees);
      },
    });
  }

  const erreur = mutation.error;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Identifiants de marché</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={enregistrer} className="space-y-4" noValidate>
          <div className="grid gap-4 sm:grid-cols-3">
            {CHAMPS.map(({ champ, libelle, aide }) => (
              <div key={champ} className="space-y-1">
                <Label htmlFor={ids[champ]}>{libelle}</Label>
                <Input
                  id={ids[champ]}
                  value={valeurs[champ]}
                  onChange={(event) => setValeurs({ ...valeurs, [champ]: event.target.value })}
                  aria-invalid={erreur instanceof ApiError && Boolean(erreur.fields?.[champ])}
                />
                <p className="text-xs text-brand-grey">
                  {erreur instanceof ApiError && erreur.fields?.[champ]
                    ? erreur.fields[champ]
                    : aide}
                </p>
              </div>
            ))}
          </div>
          {erreur && !(erreur instanceof ApiError && erreur.fields) ? (
            <Alert variant="destructive">
              <AlertDescription>
                {erreur instanceof ApiError && erreur.code === "identifiant_deja_utilise"
                  ? "Cet identifiant est déjà attribué à une autre entreprise."
                  : erreur.message}
              </AlertDescription>
            </Alert>
          ) : null}
          {mutation.isSuccess && modifies.length === 0 ? (
            <p role="status" className="text-sm text-brand-grey">
              Identifiants enregistrés.
            </p>
          ) : null}
          <Button type="submit" disabled={modifies.length === 0 || mutation.isPending}>
            {mutation.isPending ? "Enregistrement..." : "Enregistrer les identifiants"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
