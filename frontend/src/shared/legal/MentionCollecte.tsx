import { Link } from "react-router-dom";

/** Information au moment de la collecte (RGPD, art. 13), sous le bouton d'envoi de chaque
 * formulaire public : qui traite les données, pourquoi, et où lire le détail. Aucune case à
 * cocher : la base légale n'est pas le consentement (mesures précontractuelles, intérêt
 * légitime), voir features/legal/components/PolitiqueConfidentialitePage.tsx. */
export function MentionCollecte({ finalite }: { finalite: string }) {
  return (
    <p className="text-xs leading-5 text-muted-foreground">
      Les informations saisies sont traitées par l’équipe GreenFinance-Scorer {finalite}. Pour en
      savoir plus et exercer vos droits, consultez la{" "}
      <Link to="/confidentialite" className="font-medium text-primary underline underline-offset-2">
        politique de confidentialité
      </Link>
      .
    </p>
  );
}
