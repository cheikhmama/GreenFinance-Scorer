# Architecture Frontend — GreenFinance-Scorer

Ce document est le contrat d'architecture du frontend. Il décrit des règles vérifiables, pas seulement des
intentions. Toute modification structurelle du frontend doit mettre à jour ce document dans le même commit.

**Statut au 2026-08-19 : Auth MVP — Étape 9 partielle.** `frontend/` existe et est fonctionnel pour le socle
d'authentification : connexion, session via cookie `httpOnly`, `RequireRole`, six tableaux de bord placeholder
(un par espace, sans logique métier). **MFA, CSRF, révocation/rotation des sessions et durcissement production
restent à faire** — voir §4.2 pour le détail de chaque point. Tout le reste de ce document (§2.1 espaces
métier, §3.1 client généré Orval, etc.) reste au stade « cible » : les mentions « cible » ci-dessous ne doivent
jamais être présentées comme déjà livrées tant que ce statut n'a pas été mis à jour dans le même commit que le
code correspondant.

**Atelier UI multi-acteurs au 2026-08-20.** Un prototype interactif isolé est disponible sous
`/prototype/*` dans `features/prototype/`. Il utilise exclusivement des données synthétiques partagées et ne
contourne ni `/auth/me`, ni `RequireRole`, ni les routes métier protégées. Il permet d'évaluer les six espaces,
les formulaires et les transitions inter-acteurs avant connexion aux API. Il est activé en développement et
uniquement sur demande dans un build de démonstration avec `VITE_ENABLE_PROTOTYPE=true`. Il ne constitue pas
une implémentation des services backend décrits comme « cible » dans ce document.

## 0. Vision produit et principes non négociables

Le frontend est l'interface de décision d'une plateforme ESG et carbone. Sa qualité ne se mesure donc pas au
nombre de graphiques, mais à la capacité de répondre rapidement à quatre questions :

1. **Quelle est la valeur ?** Score, émission, statut ou décision, avec son unité et sa période.
2. **D'où vient-elle ?** Rapport, page, extrait et méthode de calcul accessibles sans perdre le contexte.
3. **Quel est son niveau de confiance ?** Donnée rapportée, calculée ou estimée, statut d'audit et éventuelle
   anomalie, jamais exprimés uniquement par une couleur.
4. **Que puis-je faire maintenant ?** Une action principale claire, autorisée par le rôle courant et dont le
   résultat est confirmé explicitement.

Les principes suivants s'appliquent à tous les espaces :

- **preuve avant décoration** : toute métrique importante mène à sa justification documentaire ;
- **exactitude avant densité** : période, devise, unité et méthode accompagnent toujours une valeur ;
- **divulgation progressive** : synthèse d'abord, détails et méthode à la demande ;
- **accessibilité native** : clavier, lecteur d'écran, contraste et réduction des animations dès le premier
  composant ;
- **sécurité côté serveur** : le frontend améliore l'ergonomie mais ne décide jamais seul d'une autorisation ;
- **états complets** : chaque vue asynchrone prévoit chargement, absence de données, succès, erreur et accès
  interdit ;
- **simplicité mesurée** : aucune dépendance, abstraction ou globalisation d'état sans besoin démontré.

## 1. Périmètre et décisions techniques

### 1.1 Application

- **SPA privée** : Vite + React + TypeScript en mode strict. Les six espaces sont derrière authentification ;
  aucun rendu serveur n'est requis pour le référencement.
- **Navigation** : React Router, avec découpage par route et chargement différé de chaque espace. Une erreur de
  chargement d'un module ne doit pas rendre toute l'application inutilisable.
- **Production** : fichiers statiques servis derrière le même domaine que `/api/v1` lorsque c'est possible. Il
  n'existe aucun runtime Node en production.
- **Navigateurs cibles** : les deux dernières versions stables de Chrome, Edge, Firefox et Safari. Toute
  fonctionnalité non disponible sur cette matrice doit être remplacée ou explicitement polyfillée.
- **Langue** : interface française par défaut. Les textes applicatifs sont centralisés dès le début ; dates,
  nombres, pourcentages et devises passent par `Intl`, jamais par concaténation manuelle.

Streamlit reste limité aux outils internes de validation data (Docling, bge-m3/FAISS et vérité terrain). Il ne
fait pas partie de l'application livrée et ne vit pas dans `frontend/`.

### 1.2 Bibliothèques retenues

| Besoin | Choix | Règle |
|---|---|---|
| Construction | Vite + React + TypeScript | versions exactes verrouillées dans le lockfile |
| Navigation | React Router | routes déclarées par feature, chargées paresseusement |
| État serveur | TanStack Query | source unique pour les données de l'API |
| Formulaires | React Hook Form + Zod | schéma partagé entre validation et affichage des erreurs |
| UI | Tailwind CSS + shadcn/ui | primitives possédées par le projet et accessibles |
| Tableaux | TanStack Table | tri/filtrage serveur pour les grands jeux de données |
| Dashboards | Tremor | uniquement pour les visualisations standards |
| Visualisations avancées | visx | waterfall ou Sankey non couverts par Tremor |
| PDF | react-pdf | chargé uniquement sur les routes qui affichent une preuve |
| Tests | Vitest + Testing Library + MSW + Playwright | niveaux de tests séparés, responsabilités distinctes |

Un second outil remplissant le même rôle n'est pas ajouté. Zustand n'est introduit que si un état UI réellement
transverse ne peut vivre ni dans l'URL, ni dans un composant, ni dans TanStack Query.

## 2. Architecture cible

```text
frontend/
├── public/
├── src/
│   ├── app/
│   │   ├── App.tsx                 # composition racine, aucun métier
│   │   ├── providers.tsx           # QueryClient, routeur, thème, notifications
│   │   ├── router.tsx              # assemblage des routes publiques et privées
│   │   └── styles.css              # tokens et styles globaux minimaux
│   ├── features/
│   │   ├── auth/
│   │   ├── admin/
│   │   ├── company/
│   │   ├── audit/
│   │   ├── investor/
│   │   ├── researcher/
│   │   └── institution/
│   ├── shared/
│   │   ├── api/                    # transport, client généré, erreurs et query keys
│   │   ├── auth/                   # RequireAuth/RequireRole sans logique backend
│   │   ├── charts/                 # primitives de graphiques réellement transverses
│   │   ├── config/                 # configuration publique validée au démarrage
│   │   ├── errors/                 # ErrorBoundary et présentation des erreurs
│   │   ├── format/                 # unités, dates, devises et pourcentages
│   │   ├── layout/                 # shell, navigation, skip link et fil d'Ariane
│   │   ├── pdf/                    # visualiseur de preuve documentaire
│   │   ├── testing/                # render helpers, factories et serveur MSW
│   │   └── ui/                     # primitives génériques du design system
│   ├── main.tsx
│   └── vite-env.d.ts
├── e2e/
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

### 2.1 Correspondance fonctionnelle

| Module frontend | Responsabilité | Backend | Étape |
|---|---|---|---|
| `features/auth/` | connexion, session, déconnexion | `app/auth/` | 9 |
| `features/admin/` | administration et file de revue | `app/admin/` | 10 |
| `features/company/` | dépôt de rapports et données extraites | `app/company/` | 10 |
| `features/audit/` | affectations, avis et preuves | `app/audit/` | 11 |
| `features/investor/` | portefeuille, scores et agrégations | `app/investor/` | 15–16 |
| `features/researcher/` | exploration et exports autorisés | `app/researcher/` | 17 |
| `features/institution/` | supervision institutionnelle | `app/institution/` | 17 |

`ingestion`, `scoring`, `carbon` et `explainability` ne deviennent pas des features frontend autonomes. Leurs
résultats sont présentés dans l'espace qui porte le parcours utilisateur correspondant.

### 2.2 Structure d'une feature

Une feature contient uniquement ce qu'elle possède :

```text
features/company/
├── api/                 # options de requêtes, mutations et query keys
├── components/          # composants propres à l'espace Entreprise
├── pages/               # composants associés aux routes
├── schemas/             # formulaires et validations propres à la feature
├── routes.tsx           # routes et rôles admis
└── index.ts             # API publique minimale de la feature
```

Règles de dépendance :

- `app` peut importer `features` et `shared` ;
- une `feature` peut importer `shared`, jamais une autre feature ;
- `shared` n'importe jamais `features` ni `app` ;
- les imports externes passent par le `index.ts` public d'une feature ;
- les alias autorisés sont `@/app`, `@/features` et `@/shared` ; pas de chemins relatifs traversant plusieurs
  niveaux ;
- ces frontières sont vérifiées par ESLint, pas seulement documentées.

Un élément commence dans la feature qui l'utilise. Il ne remonte dans `shared/` qu'après au moins deux usages
réels et si son vocabulaire est indépendant du métier.

## 3. Contrat API et gestion des données

### 3.1 Client typé

- La source de vérité est `/api/v1/openapi.json`.
- Le client TypeScript est généré avec **Orval** dans `src/shared/api/generated/`. Ce dossier n'est jamais édité
  manuellement et reste committé pour rendre les changements de contrat visibles en revue.
- Un adaptateur de transport unique ajoute `credentials: "include"`, le jeton CSRF, le délai maximal, le
  décodage de l'erreur standard et le `correlation_id`.
- Une commande `npm run api:generate` régénère le client ; `npm run api:check` échoue si le dépôt ne correspond
  plus au schéma OpenAPI.
- Les composants n'importent jamais le client généré. Chaque feature expose des options TanStack Query et des
  mutations depuis son dossier `api/`.

**Exception transitoire, actuellement en vigueur — limitée à `features/auth/` :** `shared/api/client.ts` est un
client `fetch` écrit à la main, pas généré par Orval. Justification : à l'Étape 9 partielle, l'API n'expose que
trois routes (`login`, `me`, `logout`) — générer un client à partir d'un schéma OpenAPI qui ne décrit quasiment
aucune route métier n'apporterait rien de plus qu'un appel `fetch` direct avec `credentials: "include"`. Cette
exception **s'arrête dès les premières routes métier** (Étape 10, `app/company` ou `app/admin`) : à ce
moment-là, `client.ts` est retiré et remplacé par le client Orval décrit ci-dessus, sans exception résiduelle
pour `auth`.

Les `operationId` FastAPI doivent être explicites et stables : les renommer constitue une rupture de contrat.
Les réponses paginées utilisent partout la même forme et les mêmes paramètres. Une mutation est invalide si
elle ne déclare pas précisément les query keys à invalider ou mettre à jour.

### 3.2 Répartition de l'état

| Type d'état | Emplacement |
|---|---|
| Donnée venant du serveur | TanStack Query |
| Filtre, tri, page, onglet partageable | URL |
| Champ de formulaire | React Hook Form |
| Ouverture locale, sélection temporaire | composant React |
| Préférence UI transverse persistante | store dédié, seulement si nécessaire |

Les valeurs serveur ne sont jamais copiées dans un store global. Les valeurs calculables ne sont pas stockées.
Les query keys sont des fabriques typées et centralisées par domaine.

TanStack Query est configuré intentionnellement : aucune relance sur `400`, `401`, `403` ou `404`; relance
bornée avec temporisation pour les erreurs réseau et `5xx`; `staleTime` défini selon la volatilité métier ;
polling uniquement pour un traitement asynchrone actif et arrêté dès son état terminal.

### 3.3 Erreurs et résilience

Le backend renvoie :

```json
{"error":{"code":"invalid_credentials","message":"Identifiants invalides.","correlation_id":"…"}}
```

Le frontend transforme cette réponse en `ApiError` typée. Il affiche un message utile, une action de reprise et
le `correlation_id` copiable dans les vues d'erreur. Il ne montre ni stack trace, ni payload brut, ni détail
technique sensible.

- `401` : vider les données privées du cache, mémoriser une destination interne sûre, puis afficher la connexion ;
- `403` : conserver la session et afficher une page « accès non autorisé » ;
- `404` : afficher une absence contextualisée, sans redirection silencieuse ;
- `409/422` : rattacher les erreurs de validation aux champs concernés lorsque le contrat le permet ;
- erreur imprévue : `ErrorBoundary` par route, avec possibilité de réessayer ;
- perte réseau : bannière non bloquante et conservation des saisies non sensibles.

## 4. Authentification et sécurité

### 4.1 Contrat Étape 9

**Statut : Auth MVP — Étape 9 partielle**, livré et fonctionnel pour le contrat ci-dessous ; MFA, CSRF et
révocation/rotation de session restent à faire (§4.2). Le contrat initial est :

- `POST /api/v1/auth/login` — ouvre une session et retourne `UtilisateurPublic` ;
- `GET /api/v1/auth/me` — retourne l'utilisateur courant ;
- `POST /api/v1/auth/logout` — ferme la session ;
- rôles : `ADMINISTRATEUR`, `ENTREPRISE`, `AUDITEUR`, `INVESTISSEUR`, `CHERCHEUR`, `INSTITUTION`.

Le JWT reste exclusivement dans un cookie `httpOnly`; il n'est jamais copié dans `localStorage`,
`sessionStorage`, l'état React, les logs ou un outil d'analytics. Le client utilise toujours
`credentials: "include"`.

### 4.2 Protection de session

`SameSite=Lax` constitue une défense supplémentaire mais ne remplace pas à lui seul une protection CSRF. Avant
toute mise en production, les requêtes mutantes doivent utiliser un jeton CSRF lié à la session, envoyé dans un
en-tête dédié et vérifié par le backend. Si le déploiement le permet, le cookie de session cible est
`__Host-access_token`, avec `Secure`, `httpOnly`, `Path=/` et aucun attribut `Domain`.

Les exigences complémentaires sont :

- aucune route `GET` ne modifie l'état ;
- validation stricte de `Origin`/`Referer` sur les requêtes mutantes ;
- limitation des tentatives de connexion côté backend ;
- rotation/révocation de session et MFA traitées avant le niveau production attendu ;
- CSP restrictive, en-têtes de sécurité, dépendances auditées et absence de secret dans le bundle ;
- redirection après connexion limitée à un chemin interne connu pour empêcher les redirections ouvertes.

`RequireAuth` et `RequireRole` améliorent la navigation mais ne sont jamais considérés comme une barrière de
sécurité. Toutes les routes API restent protégées par `get_current_user` et `require_role` côté FastAPI.

## 5. Expérience utilisateur et design system

### 5.1 Fondations visuelles

Les couleurs de marque (`#0f6b4f`, `#16324f`, `#5b6573`) deviennent des tokens sémantiques — `surface`,
`text`, `primary`, `success`, `warning`, `danger`, `border`, `focus` — avec variantes clair/sombre si un thème
sombre est réellement livré. Un composant ne consomme jamais directement une couleur de marque.

Le système définit aussi typographie, grille d'espacement, rayons, ombres, niveaux d'élévation, largeurs de
contenu et durées d'animation. Les primitives shadcn/ui sont adaptées une seule fois dans `shared/ui/`.

Chaque page suit une hiérarchie stable : titre et contexte, action principale, indicateurs essentiels, contenu
détaillé, puis métadonnées. Les actions destructives sont visuellement distinctes, confirmées et réversibles
lorsque possible.

### 5.2 Données ESG et carbone

- Une valeur affiche systématiquement unité, période, périmètre et méthode (`RAPPORTEE`, `CALCULEE`, `ESTIMEE`).
- Un score affiche la version de configuration utilisée et permet d'ouvrir sa décomposition.
- Un statut combine libellé, icône et couleur ; la couleur seule ne transmet aucune information.
- Un graphique dispose d'un titre conclusif, d'axes et unités explicites, d'une légende, d'un résumé textuel et
  d'une table accessible ou d'un équivalent téléchargeable.
- Les comparaisons ne mélangent jamais silencieusement devises, périodes ou unités.
- Les nombres conservent leur précision métier ; l'arrondi d'affichage ne modifie jamais la valeur source.

### 5.3 Responsive et états d'interface

L'application est **desktop-first mais pleinement exploitable sur tablette**. Les parcours essentiels
(connexion, consultation d'un score, ouverture d'une preuve, décision d'audit) restent utilisables sur mobile.
Une grande table devient une vue adaptée ou défile horizontalement avec en-têtes conservés ; elle n'est jamais
compressée jusqu'à devenir illisible.

Les skeletons reproduisent la structure finale et n'apparaissent pas pour une transition instantanée. Une page
vide explique pourquoi elle est vide et propose l'action pertinente. Toute mutation empêche le double envoi,
annonce son avancement et confirme son résultat.

## 6. Accessibilité

La cible est **WCAG 2.2 niveau AA** :

- HTML sémantique avant ARIA ;
- navigation clavier complète, ordre de focus logique et focus toujours visible ;
- lien d'évitement vers le contenu principal ;
- modales avec piégeage et restitution correcte du focus ;
- labels persistants, erreurs reliées aux champs et résumé d'erreurs ;
- annonces `aria-live` sobres pour mutations et traitements asynchrones ;
- contrastes AA, cibles tactiles suffisantes et respect de `prefers-reduced-motion` ;
- authentification compatible avec les gestionnaires de mots de passe et le copier-coller ;
- test automatique axe complété par des tests clavier et lecteur d'écran sur les parcours critiques.

Une réussite au scanner automatique n'est pas considérée comme une preuve suffisante d'accessibilité.

## 7. Preuve documentaire et visualiseur PDF

`shared/pdf/` reçoit une référence stable `(document_id, page)` ; il ne reçoit jamais un chemin de stockage ou
une URL arbitraire fournie directement par l'utilisateur. Le backend vérifie l'autorisation avant de diffuser
le document ou de produire une URL courte durée.

Le visualiseur :

- ouvre directement la page citée et la met visuellement en contexte ;
- conserve numéro de page, zoom, recherche et téléchargement selon les permissions ;
- affiche l'extrait textuel associé à côté du document ;
- fonctionne au clavier et fournit une alternative textuelle ;
- charge PDF.js et les documents seulement à la demande ;
- révoque les object URLs, borne la taille traitée et gère explicitement fichier absent, corrompu ou interdit ;
- n'injecte jamais le contenu extrait comme HTML non assaini.

L'objectif UX est de passer d'une métrique à sa preuve en un clic, puis de revenir exactement au contexte
initial.

## 8. Performance

Les budgets initiaux, mesurés sur un build de production, sont :

- shell de connexion et d'application ≤ **250 Ko gzip** de JavaScript initial, hors chunks PDF/graphiques ;
- aucun chunk de route ≥ **500 Ko gzip** sans justification documentée ;
- PDF, graphiques avancés et espaces métier chargés paresseusement ;
- listes volumineuses paginées côté serveur et virtualisées seulement après mesure ;
- images dimensionnées, compressées et sans décalage de mise en page ;
- score Lighthouse CI ≥ **90** pour performance, accessibilité et bonnes pratiques sur les pages de référence.

Les Web Vitals sont mesurés avec des données dépourvues de PII. Une régression de budget bloque la CI ou exige
une décision d'architecture explicitement documentée.

## 9. Tests et stratégie qualité

| Niveau | Outils | Ce qu'il prouve |
|---|---|---|
| Unitaire | Vitest | formatage, schémas, query keys, règles pures |
| Composant | Testing Library + MSW | comportement utilisateur et états API |
| Accessibilité | axe + tests manuels ciblés | défauts automatiques et parcours clavier |
| Contrat | OpenAPI + `api:check` | synchronisation backend/frontend |
| End-to-end | Playwright | parcours réels par rôle contre une API réelle |
| Visuel | captures Playwright ciblées | stabilité des primitives et pages critiques |

Principes :

- tester un comportement observable, pas l'implémentation interne ;
- désactiver les retries réseau dans les tests pour conserver des échecs rapides et déterministes ;
- un `QueryClient` neuf par test et des handlers MSW explicites ;
- aucune capture massive ni snapshot sans assertion métier ;
- données de test synthétiques, sans document ni identité de production ;
- au minimum, couvrir connexion valide/invalide, expiration de session, 403, navigation par rôle et déconnexion ;
- pour chaque feature métier, couvrir le happy path et son principal échec de sécurité ou d'intégrité.

La matrice E2E complète par rôle peut tourner séparément, mais un smoke test connexion → `/auth/me` → espace
autorisé → déconnexion bloque chaque fusion.

## 10. Observabilité et confidentialité

- Une erreur frontend reçoit un identifiant local et conserve le `correlation_id` backend lorsqu'il existe.
- Les événements techniques enregistrent route, type d'erreur, version de l'application et durée, jamais email,
  JWT, contenu de rapport, extrait PDF ou donnée ESG non publique.
- Les erreurs attendues (`401`, validation utilisateur) ne sont pas envoyées comme incidents techniques.
- Les source maps de production ne sont pas publiquement accessibles.
- La bannière globale distingue indisponibilité API, perte réseau et session expirée.
- La version frontend est visible dans l'écran de diagnostic ou les métadonnées, afin de rapprocher un incident
  du commit déployé.

## 11. Configuration et déploiement

Le bundle ne contient que de la configuration publique. Aucun secret ne porte le préfixe Vite. La configuration
publique (`API_BASE_URL`, environnement, version) est validée au démarrage ; une valeur absente produit un écran
de diagnostic explicite plutôt qu'une application partiellement fonctionnelle.

Le déploiement préféré sert SPA et API sous une même origine. En cas d'origines différentes, CORS énumère
exactement les origines autorisées, accepte les credentials et n'utilise jamais `*`. Le serveur statique renvoie
`index.html` pour les routes SPA, mais jamais pour les assets manquants ou `/api/*`.

Les assets fingerprintés reçoivent un cache long et immuable ; `index.html` reste revalidable. Le déploiement
est atomique et la version précédente doit pouvoir être restaurée.

## 12. Portes CI et Definition of Done

Une modification frontend n'est fusionnable que si :

1. formatage, ESLint et vérification des frontières d'import sont verts ;
2. TypeScript strict ne produit aucune erreur et aucun `any` non justifié ;
3. tests unitaires/composants et smoke E2E sont verts ;
4. le build de production réussit et respecte les budgets ;
5. `api:check` confirme la synchronisation OpenAPI ;
6. axe ne détecte aucune violation sérieuse ou critique sur les pages touchées ;
7. les états loading/empty/error/forbidden ont été traités ;
8. la vue a été vérifiée au clavier et aux largeurs mobile, tablette et desktop ;
9. aucun secret, token, PII ou contenu documentaire n'apparaît dans les logs ou le bundle ;
10. toute nouvelle convention est reflétée dans ce document.

## 13. Ordre de livraison

### Étape 9 — fondation et authentification

1. Vite/React/TypeScript strict, outils qualité et CI ;
2. tokens, primitives UI et shell accessible ;
3. client OpenAPI, transport, `ApiError` et MSW ;
4. login, `/auth/me`, logout, `RequireAuth` et `RequireRole` ;
5. CSRF et durcissement des cookies avant toute exposition de production ;
6. tests de session, 401/403, accessibilité et smoke Playwright.

### Étapes suivantes

Chaque espace est livré verticalement : contrat API → route → états UI → preuve documentaire → permissions →
tests → observabilité. Aucun écran métier n'est construit contre un contrat fictif durable ; MSW simule le
contrat OpenAPI réel ou explicitement approuvé.

## 14. Décisions à ne pas rouvrir sans ADR

- SPA statique plutôt que SSR ;
- organisation par espace utilisateur plutôt que par couche technique ;
- OpenAPI comme source du client ;
- cookie `httpOnly` plutôt que stockage JavaScript du JWT ;
- TanStack Query comme propriétaire de l'état serveur ;
- WCAG 2.2 AA comme seuil ;
- un seul visualiseur de preuve et un seul design system.

Toute remise en cause doit prendre la forme d'un ADR court : contexte, options, décision, conséquences et plan
de migration.
