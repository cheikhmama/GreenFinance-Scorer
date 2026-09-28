import { useSearchParams } from "react-router-dom";
import { PageHeader } from "@/shared/ui/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { AllCompaniesSection } from "./AllCompaniesSection";
import { CompaniesToRepublishSection } from "./CompaniesToRepublishSection";
import { CompanyScoresSection } from "./CompanyScoresSection";
import { PublishableCompaniesSection } from "./PublishableCompaniesSection";

type Onglet = "inscrites" | "publiables" | "a-republier" | "scores";
const ONGLET_PAR_DEFAUT: Onglet = "inscrites";
const ONGLETS_VALIDES: Onglet[] = ["inscrites", "publiables", "a-republier", "scores"];

/** Trois catégories d'entreprises répondant chacune à un critère distinct (inscrite ≠ publiable
 * ≠ à republier — une entreprise peut relever de plusieurs à la fois) : les empiler sur une même
 * page mélangeait ces listes au lieu de les distinguer clairement. `onglet` dans l'URL permet aux
 * cartes du tableau de bord Admin de déposer directement sur la bonne catégorie plutôt que sur
 * une page qu'il faut ensuite trier soi-même. */
export function AdminCompaniesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const parametre = searchParams.get("onglet");
  const onglet: Onglet = ONGLETS_VALIDES.includes(parametre as Onglet)
    ? (parametre as Onglet)
    : ONGLET_PAR_DEFAUT;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Entreprises"
        description="Suivi de toutes les entreprises, et publication de celles prêtes à l'être."
      />
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
          <TabsTrigger value="inscrites">Entreprises inscrites</TabsTrigger>
          <TabsTrigger value="publiables">Publiables</TabsTrigger>
          <TabsTrigger value="a-republier">À republier</TabsTrigger>
          <TabsTrigger value="scores">Scores ESG</TabsTrigger>
        </TabsList>
        <TabsContent value="inscrites">
          <AllCompaniesSection />
        </TabsContent>
        <TabsContent value="publiables">
          <PublishableCompaniesSection />
        </TabsContent>
        <TabsContent value="a-republier">
          <CompaniesToRepublishSection />
        </TabsContent>
        <TabsContent value="scores">
          <CompanyScoresSection />
        </TabsContent>
      </Tabs>
    </div>
  );
}
