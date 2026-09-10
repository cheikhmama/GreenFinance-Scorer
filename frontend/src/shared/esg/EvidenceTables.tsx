import type {
  DonneeCarboneDetail,
  IndicateurESGDetail,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";

/** Tableaux indicateurs ESG / données carbone avec leur preuve documentaire — même forme que
 * features/company/components/CompanyReportDetailPage.tsx, partagée ici pour les espaces
 * Investisseur et Chercheur (deux nouveaux usages réels, voir FRONTEND-ARCHITECTURE.md §2.2). */
export function IndicatorsTable({ indicateurs }: { indicateurs: IndicateurESGDetail[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Indicateurs ESG</CardTitle>
      </CardHeader>
      <CardContent>
        {indicateurs.length === 0 ? (
          <p className="text-brand-grey">Aucun indicateur disponible.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-brand-grey">
                  <th className="py-2 pr-4 font-medium">Pilier</th>
                  <th className="py-2 pr-4 font-medium">Code</th>
                  <th className="py-2 pr-4 font-medium">Valeur</th>
                  <th className="py-2 font-medium">Preuve (source)</th>
                </tr>
              </thead>
              <tbody>
                {indicateurs.map((indicateur) => (
                  <tr key={indicateur.id} className="border-b last:border-0">
                    <td className="py-2 pr-4">{indicateur.pilier}</td>
                    <td className="py-2 pr-4">{indicateur.code}</td>
                    <td className="py-2 pr-4">
                      {indicateur.valeur} {indicateur.unite}
                    </td>
                    <td className="py-2 text-brand-grey">
                      {indicateur.preuve.nom_document} — p.{indicateur.preuve.page_debut}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function CarbonTable({ donneesCarbone }: { donneesCarbone: DonneeCarboneDetail[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Données carbone (Scope 1/2/3)</CardTitle>
      </CardHeader>
      <CardContent>
        {donneesCarbone.length === 0 ? (
          <p className="text-brand-grey">Aucune donnée carbone disponible.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-brand-grey">
                  <th className="py-2 pr-4 font-medium">Scope</th>
                  <th className="py-2 pr-4 font-medium">Valeur</th>
                  <th className="py-2 font-medium">Preuve (source)</th>
                </tr>
              </thead>
              <tbody>
                {donneesCarbone.map((donnee) => (
                  <tr key={donnee.id} className="border-b last:border-0">
                    <td className="py-2 pr-4">
                      Scope {donnee.scope}
                      {donnee.categorie_ges ? ` — ${donnee.categorie_ges}` : ""}
                    </td>
                    <td className="py-2 pr-4">{donnee.valeur_tonnes_co2e.toLocaleString("fr-FR")} tCO2e</td>
                    <td className="py-2 text-brand-grey">
                      {donnee.preuve.nom_document} — p.{donnee.preuve.page_debut}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
