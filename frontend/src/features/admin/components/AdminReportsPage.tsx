import { useSearchParams } from "react-router-dom";
import { PageHeader } from "@/shared/ui/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { RapportsTable } from "./RapportsTable";

type Onglet = "tous" | "alertes" | "a-affecter" | "en-validation";
const ONGLET_PAR_DEFAUT: Onglet = "tous";
const ONGLETS_VALIDES: Onglet[] = ["tous", "alertes", "a-affecter", "en-validation"];

/** Quatre catégories de rapports répondant chacune à un critère distinct de la même entité
 * (un rapport n'appartient jamais à deux à la fois) : les empiler sur une même page mélangeait
 * ces files au lieu de les distinguer clairement. `onglet` dans l'URL permet aux cartes du
 * tableau de bord Admin de déposer directement sur la bonne catégorie. */
export function AdminReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const parametre = searchParams.get("onglet");
  const onglet: Onglet = ONGLETS_VALIDES.includes(parametre as Onglet)
    ? (parametre as Onglet)
    : ONGLET_PAR_DEFAUT;

  return (
    <div className="space-y-8">
      <PageHeader title="Rapports" />
      <Tabs
        value={onglet}
        onValueChange={(valeur) =>
          setSearchParams(
            (params) => {
              params.set("onglet", valeur);
              return params;
            },
            { replace: true },
          )
        }
      >
        <TabsList>
          <TabsTrigger value="tous">Tous les rapports</TabsTrigger>
          <TabsTrigger value="alertes">Alertes</TabsTrigger>
          <TabsTrigger value="a-affecter">À affecter</TabsTrigger>
          <TabsTrigger value="en-validation">En attente de décision</TabsTrigger>
        </TabsList>
        <TabsContent value="tous">
          <RapportsTable perimetre="tous" />
        </TabsContent>
        <TabsContent value="alertes">
          <RapportsTable perimetre="alertes" />
        </TabsContent>
        <TabsContent value="a-affecter">
          <RapportsTable perimetre="a-affecter" />
        </TabsContent>
        <TabsContent value="en-validation">
          <RapportsTable perimetre="en-validation" />
        </TabsContent>
      </Tabs>
    </div>
  );
}
