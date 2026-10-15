import { config } from "zod";

// Zod 4 sonde `new Function("")` pour accélérer ses validations : la CSP de production
// (deploy/Caddyfile, script-src 'self' sans 'unsafe-eval') bloque cette sonde et la signale à
// chaque page. Le mode jitless évite la sonde ; les validations restent identiques. Importé en
// premier par main.tsx : la sonde a lieu à la création des schémas, au chargement des modules.
config({ jitless: true });
