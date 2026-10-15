import { Link } from "react-router-dom";
import { AuthLayout } from "@/shared/layout/AuthLayout";
import { ACompleter } from "./ACompleter";

/** Mentions légales (loi n° 2004-575 du 21 juin 2004, LCEN, art. 6-III) : éditeur, directeur de
 * la publication, hébergeur. Les informations d'identité sont à fournir par l'exploitant. */
export function MentionsLegalesPage() {
  return (
    <AuthLayout
      layout="centered"
      eyebrow="INFORMATIONS LÉGALES"
      title="Mentions légales"
      description="Qui édite et qui héberge la plateforme GreenFinance-Scorer."
    >
      <div className="space-y-6 text-sm leading-6 text-foreground">
        <section className="space-y-2">
          <h2 className="text-base font-semibold">Éditeur</h2>
          <p>
            <ACompleter>
              dénomination (ou nom et prénom), forme juridique, capital social, adresse du siège,
              numéro RCS ou SIREN, numéro de TVA intracommunautaire
            </ACompleter>
          </p>
          <p>
            Contact : <ACompleter>adresse e-mail et numéro de téléphone</ACompleter>, ou le{" "}
            <Link to="/contact" className="font-medium text-primary underline underline-offset-2">
              formulaire de contact
            </Link>
            .
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold">Directeur de la publication</h2>
          <p>
            <ACompleter>nom et qualité</ACompleter>
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold">Hébergeur</h2>
          <p>
            Oracle Cloud Infrastructure, service de l’entité Oracle signataire du contrat :{" "}
            <ACompleter>
              dénomination, adresse et téléphone de cette entité ; région du serveur
            </ACompleter>
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold">Données personnelles</h2>
          <p>
            Le traitement des données personnelles est décrit dans la{" "}
            <Link
              to="/confidentialite"
              className="font-medium text-primary underline underline-offset-2"
            >
              politique de confidentialité
            </Link>
            .
          </p>
        </section>
      </div>
    </AuthLayout>
  );
}
