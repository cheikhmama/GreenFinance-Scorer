import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { AuthLayout } from "@/shared/layout/AuthLayout";
import { ACompleter } from "./ACompleter";

/** Politique de confidentialité (RGPD, art. 12 à 14). Décrit uniquement ce que fait réellement
 * l'application : champs collectés par chaque formulaire (app/company/router.py,
 * app/access_requests/schemas.py, app/contact/schemas.py), cookies posés par app/auth/router.py,
 * clés de localStorage du frontend. Toute évolution de ces traitements doit être reportée ici. */
export function PolitiqueConfidentialitePage() {
  return (
    <AuthLayout
      layout="centered"
      eyebrow="VOS DONNÉES"
      title="Politique de confidentialité"
      description="Quelles données la plateforme traite, pourquoi, combien de temps, et vos droits."
    >
      <div className="space-y-6 text-sm leading-6 text-foreground">
        <Section titre="Responsable du traitement">
          <p>
            <ACompleter>identité et adresse du responsable du traitement</ACompleter>. Pour toute
            question sur vos données : <ACompleter>adresse e-mail dédiée</ACompleter> (ou délégué à
            la protection des données, s’il en a été désigné un).
          </p>
        </Section>

        <Section titre="Données traitées et finalités">
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <strong>Inscription d’une entreprise</strong> : nom, secteur, pays, identifiant
              fiscal, codes ISIN et LEI, site web de l’entreprise ; nom et adresse e-mail de la
              personne de contact ; lettre de mandat signée. Finalité : vérifier la demande et créer
              le compte. Base légale : mesures précontractuelles prises à votre demande.
            </li>
            <li>
              <strong>Demande d’accès investisseur ou chercheur</strong> : nom, adresse e-mail,
              organisation, type d’investisseur ou domaine de recherche. Mêmes finalité et base
              légale.
            </li>
            <li>
              <strong>Compte</strong> : adresse e-mail, nom, rôle, photo de profil facultative, mot
              de passe (conservé uniquement sous forme hachée, jamais en clair), journal des
              connexions et déconnexions (sans adresse IP). Finalité : fournir le service et en
              assurer la sécurité. Base légale : exécution du contrat ; intérêt légitime pour la
              sécurité.
            </li>
            <li>
              <strong>Rapports ESG déposés</strong> et indicateurs qui en sont extraits. Finalité :
              calcul et publication du score ESG. Base légale : exécution du contrat.
            </li>
            <li>
              <strong>Formulaire de contact</strong> : nom, adresse e-mail, objet et message,
              transmis par e-mail à l’équipe et non enregistrés dans la base de données. Finalité :
              répondre à votre demande. Base légale : intérêt légitime.
            </li>
          </ul>
        </Section>

        <Section titre="Destinataires et sous-traitants">
          <ul className="list-disc space-y-2 pl-5">
            <li>Les équipes habilitées de la plateforme, selon leur rôle.</li>
            <li>
              Hébergement : Oracle Cloud Infrastructure,{" "}
              <ACompleter>région d’hébergement (de préférence dans l’Union européenne)</ACompleter>.
            </li>
            <li>
              Envoi des e-mails (codes de vérification, liens d’activation, notifications) :{" "}
              <ACompleter>prestataire SMTP et pays</ACompleter>.
            </li>
            <li>
              Extraction automatique des indicateurs des rapports ESG : le nom de l’entreprise et
              des extraits du rapport sont transmis à un service d’intelligence artificielle,{" "}
              <ACompleter>
                fournisseur, pays, garanties de transfert hors UE (clauses contractuelles types ou
                Data Privacy Framework) et engagement de non-réutilisation des données
              </ACompleter>
              .
            </li>
            <li>
              Vérification du code LEI d’une entreprise : le code est envoyé à la GLEIF (base
              publique des identifiants d’entités juridiques).
            </li>
          </ul>
          <p>Aucune donnée n’est vendue ni utilisée à des fins publicitaires.</p>
        </Section>

        <Section titre="Durées de conservation">
          <ul className="list-disc space-y-2 pl-5">
            <li>
              Demandes d’inscription refusées ou abandonnées, et leur lettre de mandat :{" "}
              <ACompleter>durée</ACompleter>.
            </li>
            <li>
              Comptes : pendant la relation contractuelle, puis{" "}
              <ACompleter>durée après la fermeture ou l’inactivité du compte</ACompleter>.
            </li>
            <li>
              Rapports ESG et scores publiés : <ACompleter>durée</ACompleter>.
            </li>
            <li>
              Journal des connexions : <ACompleter>durée</ACompleter>.
            </li>
          </ul>
        </Section>

        <Section titre="Cookies et stockage local">
          <p>
            La plateforme n’utilise ni cookie publicitaire ni mesure d’audience. Elle ne dépose que
            ce qui est strictement nécessaire à son fonctionnement ; aucun consentement n’est donc
            demandé.
          </p>
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <code>__Host-access_token</code> : maintient votre session après la connexion (12
              heures au plus, supprimé à la déconnexion).
            </li>
            <li>
              <code>__Host-csrf_token</code> : protège vos actions contre les requêtes frauduleuses
              émises depuis un autre site (même durée).
            </li>
            <li>
              Stockage local du navigateur : <code>gfs-theme</code> (mode clair ou sombre choisi) et{" "}
              <code>table:…</code> (préférences d’affichage des tableaux). Ces réglages restent sur
              votre appareil et ne sont jamais transmis.
            </li>
          </ul>
          <p>Les polices de caractères sont servies par la plateforme elle-même.</p>
        </Section>

        <Section titre="Vos droits">
          <p>
            Vous disposez des droits d’accès, de rectification, d’effacement, de limitation,
            d’opposition et de portabilité de vos données. Vous pouvez modifier votre nom et votre
            adresse e-mail depuis votre profil ; pour les autres demandes, écrivez à{" "}
            <ACompleter>adresse e-mail dédiée</ACompleter> ou utilisez le{" "}
            <Link to="/contact" className="font-medium text-primary underline underline-offset-2">
              formulaire de contact
            </Link>
            . Une réponse vous est apportée dans un délai d’un mois.
          </p>
          <p>
            Vous pouvez aussi introduire une réclamation auprès de la CNIL (
            <a
              href="https://www.cnil.fr/fr/plaintes"
              className="font-medium text-primary underline underline-offset-2"
              rel="noreferrer"
              target="_blank"
            >
              www.cnil.fr
            </a>
            ).
          </p>
        </Section>

        <p className="text-xs text-muted-foreground">
          Dernière mise à jour : <ACompleter>date de publication</ACompleter>.
        </p>
      </div>
    </AuthLayout>
  );
}

function Section({ titre, children }: { titre: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="text-base font-semibold">{titre}</h2>
      {children}
    </section>
  );
}
