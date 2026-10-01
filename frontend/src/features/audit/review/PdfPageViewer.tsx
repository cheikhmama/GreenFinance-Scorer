import { useEffect, useRef, useState } from "react";
import type { ProofBox } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { Skeleton } from "@/shared/ui/skeleton";

/** pdf.js chargé à la demande : seul l'espace de revue de l'Auditeur en a besoin. */
async function chargerPdfJs() {
  const [pdfjs, worker] = await Promise.all([
    import("pdfjs-dist"),
    import("pdfjs-dist/build/pdf.worker.min.mjs?url"),
  ]);
  pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
  return pdfjs;
}

/** Affiche la page-preuve d'une valeur (extrait PDF d'une page, tâche 5.5) à la largeur de son
 * conteneur, et y surligne les boîtes de la valeur citée — exprimées en fractions de la page, elles
 * suivent l'échelle d'affichage sans calcul. Sans boîte, la page entière reste la preuve. */
export function PdfPageViewer({
  url,
  boites,
  libelle,
}: {
  url: string;
  boites: ProofBox[];
  libelle: string;
}) {
  const conteneur = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [largeur, setLargeur] = useState(0);
  const [etat, setEtat] = useState<"chargement" | "pret" | "erreur">("chargement");

  useEffect(() => {
    const element = conteneur.current;
    if (!element) return;
    const observateur = new ResizeObserver(([entree]) => {
      setLargeur(Math.floor(entree.contentRect.width));
    });
    observateur.observe(element);
    return () => observateur.disconnect();
  }, []);

  useEffect(() => {
    if (largeur === 0 || !canvas.current) return;
    let annule = false;
    let tache: { cancel: () => void } | null = null;
    let chargement: { destroy: () => Promise<void> } | null = null;
    setEtat("chargement");

    (async () => {
      try {
        const pdfjs = await chargerPdfJs();
        const tacheChargement = pdfjs.getDocument({ url, withCredentials: true });
        chargement = tacheChargement;
        const pdf = await tacheChargement.promise;
        const page = await pdf.getPage(1);
        if (annule || !canvas.current) return;
        const base = page.getViewport({ scale: 1 });
        const vue = page.getViewport({ scale: largeur / base.width });
        const ratio = window.devicePixelRatio || 1;
        const cible = canvas.current;
        cible.width = Math.floor(vue.width * ratio);
        cible.height = Math.floor(vue.height * ratio);
        cible.style.width = `${Math.floor(vue.width)}px`;
        cible.style.height = `${Math.floor(vue.height)}px`;
        const rendu = page.render({
          canvas: cible,
          viewport: vue,
          transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0],
        });
        tache = rendu;
        await rendu.promise;
        if (!annule) setEtat("pret");
      } catch (erreur) {
        if (!annule && (erreur as { name?: string }).name !== "RenderingCancelledException") {
          setEtat("erreur");
        }
      }
    })();

    return () => {
      annule = true;
      tache?.cancel();
      void chargement?.destroy();
    };
  }, [url, largeur]);

  return (
    <div ref={conteneur} className="relative w-full">
      {etat === "chargement" ? <Skeleton className="absolute inset-0 min-h-96" /> : null}
      {etat === "erreur" ? (
        <p className="p-4 text-sm text-destructive">La page-preuve n’a pas pu être affichée.</p>
      ) : null}
      <div className="relative inline-block">
        <canvas ref={canvas} aria-label={`Page-preuve : ${libelle}`} role="img" />
        {etat === "pret"
          ? boites.map((boite) => (
              <div
                key={`${boite.x0}-${boite.y0}-${boite.x1}-${boite.y1}`}
                data-testid="boite-preuve"
                className="pointer-events-none absolute rounded-sm border-2 border-amber-500 bg-amber-300/30"
                style={{
                  left: `${boite.x0 * 100}%`,
                  top: `${boite.y0 * 100}%`,
                  width: `${(boite.x1 - boite.x0) * 100}%`,
                  height: `${(boite.y1 - boite.y0) * 100}%`,
                }}
              />
            ))
          : null}
      </div>
    </div>
  );
}
