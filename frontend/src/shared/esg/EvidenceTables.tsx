import { useState } from "react";
import type {
  CouvertureResume,
  DonneeCarboneDetail,
  IndicateurESGDetail,
  PreuveDocumentairePublic,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/ui/dialog";

function libellePreuve(preuve: PreuveDocumentairePublic): string {
  return preuve.page_debut === preuve.page_fin
    ? `Rapport ${preuve.annee} — page ${preuve.page_debut}`
    : `Rapport ${preuve.annee} — pages ${preuve.page_debut}-${preuve.page_fin}`;
}

/** Aperçu fluide de l'extrait PDF (une page, généré à l'ingestion — voir
 * app/ingestion/proof_generator.py) : pas d'onglet à ouvrir pour vérifier une source, l'extrait
 * s'affiche directement, avec un lien de secours pour l'ouvrir en plein onglet si besoin. */
function PreuveModal({ url, onClose }: { url: string | null; onClose: () => void }) {
  return (
    <Dialog open={url !== null} onOpenChange={(ouvert) => !ouvert && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Preuve documentaire</DialogTitle>
        </DialogHeader>
        {url ? (
          <div className="space-y-2">
            <iframe src={url} title="Preuve documentaire" className="h-[70vh] w-full rounded-md border" />
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-brand-blue underline-offset-2 hover:underline"
            >
              Ouvrir dans un nouvel onglet
            </a>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

/** Exporté (contrairement à PreuveModal, purement interne) pour les usages hors tableau — ex. la
 * preuve du score global auto-déclaré, un champ isolé plutôt qu'une ligne de tableau. */
export function PreuveLien({ preuve, url }: { preuve: PreuveDocumentairePublic; url: string }) {
  const [ouverte, setOuverte] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOuverte(true)}
        className="text-left text-brand-blue underline-offset-2 hover:underline"
      >
        {libellePreuve(preuve)}
      </button>
      <PreuveModal url={ouverte ? url : null} onClose={() => setOuverte(false)} />
    </>
  );
}

/** Regroupe les index consécutifs partageant le même pilier — index de première ligne du groupe
 * → taille du groupe. Suppose les indicateurs déjà triés par pilier (voir
 * app/investor/entreprises.py::consulter_entreprise_publiee) : un regroupement visuel sans ce
 * tri afficherait des cellules fusionnées sur des lignes qui n'ont plus rien en commun. */
function debutsDeGroupe(piliers: string[]): Map<number, number> {
  const groupes = new Map<number, number>();
  let debut = 0;
  for (let i = 1; i <= piliers.length; i++) {
    if (i === piliers.length || piliers[i] !== piliers[debut]) {
      groupes.set(debut, i - debut);
      debut = i;
    }
  }
  return groupes;
}

/** Tableaux indicateurs ESG / données carbone avec leur preuve documentaire — même forme que
 * features/company/components/CompanyReportDetailPage.tsx, partagée ici pour les espaces
 * Investisseur et Chercheur (deux nouveaux usages réels, voir FRONTEND-ARCHITECTURE.md §2.2).
 * construireUrlPreuve construit l'URL de téléchargement propre à chaque espace (préfixe
 * /investor ou /researcher) — ce composant partagé ne connaît pas cette différence. */
/** Une donnée absente doit être dite, jamais laissée à un tiret muet (décision produit — voir
 * app/ingestion/completeness.py) : "12/23 indicateurs communiqués" plutôt que de faire deviner
 * l'absence à partir de ce qui n'apparaît simplement pas dans le tableau. */
function CouvertureNote({ couverture }: { couverture: CouvertureResume }) {
  if (couverture.total_cibles === 0) return null;
  return (
    <p className="mb-3 text-sm text-brand-grey">
      {couverture.trouves}/{couverture.total_cibles} indicateurs cibles communiqués par
      l'entreprise.
      {couverture.codes_manquants.length > 0 ? (
        <span className="block text-xs">
          Non communiqués : {couverture.codes_manquants.join(", ")}
        </span>
      ) : null}
    </p>
  );
}

export function IndicatorsTable({
  indicateurs,
  couverture,
  construireUrlPreuve,
}: {
  indicateurs: IndicateurESGDetail[];
  couverture?: CouvertureResume;
  construireUrlPreuve: (preuveId: string) => string;
}) {
  const groupesPilier = debutsDeGroupe(indicateurs.map((i) => i.pilier));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Indicateurs ESG</CardTitle>
      </CardHeader>
      <CardContent>
        {couverture ? <CouvertureNote couverture={couverture} /> : null}
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
                {indicateurs.map((indicateur, i) => (
                  <tr key={indicateur.id} className="border-b last:border-0">
                    {groupesPilier.has(i) ? (
                      <td
                        className="py-2 pr-4 align-middle font-medium text-brand-blue"
                        rowSpan={groupesPilier.get(i)}
                      >
                        {indicateur.pilier}
                      </td>
                    ) : null}
                    <td className="py-2 pr-4">{indicateur.code}</td>
                    <td className="py-2 pr-4">
                      {indicateur.valeur} {indicateur.unite}
                    </td>
                    <td className="py-2">
                      <PreuveLien
                        preuve={indicateur.preuve}
                        url={construireUrlPreuve(indicateur.preuve.id)}
                      />
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

export function CarbonTable({
  donneesCarbone,
  construireUrlPreuve,
}: {
  donneesCarbone: DonneeCarboneDetail[];
  construireUrlPreuve: (preuveId: string) => string;
}) {
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
                    <td className="py-2">
                      <PreuveLien preuve={donnee.preuve} url={construireUrlPreuve(donnee.preuve.id)} />
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
