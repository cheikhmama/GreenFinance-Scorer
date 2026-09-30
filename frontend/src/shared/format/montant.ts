/** Montants au centime près (tâche 2.3) : le serveur les stocke en `numeric(20,2)` et refuse une
 * troisième décimale plutôt que de l'arrondir en silence — le formulaire le dit avant l'envoi.
 * Tolérance nécessaire : 10.1 * 100 vaut 1010.0000000000001 en virgule flottante. */
export function auPlusDeuxDecimales(valeur: number): boolean {
  const centimes = valeur * 100;
  return Math.abs(centimes - Math.round(centimes)) < 1e-6;
}

export const MESSAGE_DEUX_DECIMALES = "Au plus deux décimales.";
