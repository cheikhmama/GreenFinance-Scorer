import { CheckCircle2 } from "lucide-react";
import { Badge } from "@/shared/ui/badge";
import { Skeleton } from "@/shared/ui/skeleton";
import { useMyCompanyProfile, useMyLeiVerification } from "../api";

/** En-tête de l'espace Entreprise (tâche 5.9) : le nom légal de l'entreprise connectée, puis ses
 * métadonnées en badges — secteur, LEI, ISIN — telles que déclarées. « GLEIF Validé » n'apparaît
 * que si la GLEIF confirme en direct l'enregistrement et le nom légal ; une donnée absente n'est
 * jamais remplacée par une valeur inventée. */
export function CompanyIdentityHeader() {
  const { data: entreprise, isPending } = useMyCompanyProfile();
  const verification = useMyLeiVerification(entreprise?.lei);

  if (isPending) return <Skeleton className="h-16 w-2/3" />;
  if (!entreprise) return null;

  return (
    <header className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">{entreprise.name}</h1>
        {verification.data?.result === "PASSED" ? (
          <Badge variant="success" title={verification.data.detail}>
            <CheckCircle2 className="size-3" aria-hidden="true" />
            GLEIF Validé
          </Badge>
        ) : null}
        {verification.data?.result === "FAILED" ? (
          <Badge variant="warning" title={verification.data.detail}>
            LEI non confirmé par la GLEIF
          </Badge>
        ) : null}
      </div>
      <ul aria-label="Identité de l’entreprise" className="flex flex-wrap gap-2">
        <li>
          <Badge variant="outline" className="font-normal text-muted-foreground">
            Secteur : <span className="font-medium text-foreground">{entreprise.sector}</span>
          </Badge>
        </li>
        {entreprise.lei ? (
          <li>
            <Badge variant="outline" className="font-normal text-muted-foreground">
              LEI : <code className="font-mono text-foreground">{entreprise.lei}</code>
            </Badge>
          </li>
        ) : null}
        {entreprise.isin ? (
          <li>
            <Badge variant="outline" className="font-normal text-muted-foreground">
              ISIN : <code className="font-mono text-foreground">{entreprise.isin}</code>
            </Badge>
          </li>
        ) : null}
      </ul>
    </header>
  );
}
