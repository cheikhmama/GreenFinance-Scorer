import { useQuery } from "@tanstack/react-query";
import { Link, Outlet, useNavigate, useParams } from "react-router-dom";
import { formatValeur, libelleMethode, libellePilier } from "@/shared/format/indicateurs";
import { libelleStatutRevue } from "@/shared/format/revue";
import { idDepuisSlug } from "@/shared/format/slug";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent } from "@/shared/ui/card";
import { DisclosureCard } from "@/shared/ui/disclosure-card";
import { rapportQueryOptions } from "../api";
import { FAMILLE_AUTRES, type Famille, famillesDuPilier, pilierDepuisSlug } from "../esg/taxonomie";
import { type MetriqueVue, metriquesDuRapport } from "../esg/vueMetrique";

function resumeFamille(famille: Famille, lignes: MetriqueVue[]): string {
  if (lignes.length === 0) return "Aucun indicateur trouvé";
  const attendus = famille.slug === FAMILLE_AUTRES ? lignes.length : famille.codes.length;
  const trouves = new Set(lignes.map((m) => m.cle)).size;
  const enRevue = lignes.filter((m) => m.revue === "PENDING").length;
  const parties = [`${trouves}/${attendus} trouvé(s)`];
  if (enRevue > 0) parties.push(`${enRevue} en revue`);
  if (famille.slug === "emissions-ges") {
    const valeur = (cle: string) => lignes.find((m) => m.cle === cle)?.valeur;
    const scope1 = valeur("scope_1");
    const scope2 = valeur("scope_2_market_based") ?? valeur("scope_2");
    if (scope1 !== undefined && scope2 !== undefined) {
      parties.push(`Scopes 1 + 2 : ${formatValeur(scope1 + scope2, "tCO2e")}`);
    }
  }
  return parties.join(" · ");
}

export function SectionIntrouvable({ texte }: { texte: string }) {
  return (
    <Card>
      <CardContent className="space-y-2 py-6 text-center">
        <p className="font-medium text-foreground">Section introuvable</p>
        <p className="text-sm text-muted-foreground">{texte}</p>
        <Link to=".." relative="path" className="text-sm underline">
          Revenir à la déclaration
        </Link>
      </CardContent>
    </Card>
  );
}

/** Niveau 4 (spec §2.2) : un pilier, une carte repliable par famille. La famille ouverte est
 * dans l'URL (…/:pilier/:famille) ; un indicateur s'ouvre en tiroir (…/:famille/:code). */
export function PillarPage() {
  const { rapportId: segment = "", pilier: slug, famille: familleOuverte } = useParams();
  const navigate = useNavigate();
  const pilier = pilierDepuisSlug(slug);
  const { data: metriques } = useQuery({
    ...rapportQueryOptions(idDepuisSlug(segment)),
    select: metriquesDuRapport,
  });
  if (!pilier) return <SectionIntrouvable texte="Ce pilier n’existe pas." />;
  if (!metriques) return null;

  const base = `/company/declarations/${segment}/${slug}`;
  const familles = famillesDuPilier(pilier)
    .map((famille) => ({
      famille,
      lignes: metriques.filter((m) => m.pilier === pilier && m.famille === famille.slug),
    }))
    .filter(({ famille, lignes }) => famille.slug !== FAMILLE_AUTRES || lignes.length > 0);
  const familleInconnue =
    familleOuverte !== undefined &&
    !familles.some(({ famille }) => famille.slug === familleOuverte);

  return (
    <section aria-labelledby="titre-pilier" className="space-y-4">
      <h2 id="titre-pilier" className="text-lg font-semibold text-foreground">
        {libellePilier(pilier)}
      </h2>
      {familleInconnue ? (
        <Alert>
          <AlertDescription>
            Cette famille d’indicateurs n’existe pas dans ce pilier.
          </AlertDescription>
        </Alert>
      ) : null}
      {familles.map(({ famille, lignes }) => (
        <DisclosureCard
          key={famille.slug}
          id={`famille-${famille.slug}`}
          titre={famille.libelle}
          resume={resumeFamille(famille, lignes)}
          ouvert={familleOuverte === famille.slug}
          onOuvertChange={(ouvert) =>
            navigate(ouvert ? `${base}/${famille.slug}` : base, { preventScrollReset: true })
          }
        >
          {lignes.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Aucune valeur de cette famille n’a été trouvée dans le rapport.
            </p>
          ) : (
            <ul className="divide-y">
              {lignes.map((m) => (
                <li key={m.id}>
                  <Link
                    to={`${base}/${famille.slug}/${m.cle}`}
                    preventScrollReset
                    className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <span className="font-medium text-foreground">{m.libelle}</span>
                    <span className="flex items-center gap-2 tabular-nums">
                      {formatValeur(m.valeur, m.unite)}
                      {m.periode !== null ? (
                        <span className="text-muted-foreground">· {m.periode}</span>
                      ) : null}
                      <Badge variant="outline">{libelleMethode(m.methode)}</Badge>
                      {m.revue ? (
                        <Badge variant="secondary">{libelleStatutRevue(m.revue)}</Badge>
                      ) : null}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </DisclosureCard>
      ))}
      <Outlet />
    </section>
  );
}
