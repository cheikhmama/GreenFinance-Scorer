# Rapport de test — GreenFinance-Scorer

Checklist de test manuel couvrant les 6 espaces de la plateforme et les parcours publics, construite
sur le jeu de données de démonstration (`greenfinance_demo`). Coche au fur et à mesure
(`- [ ]` → `- [x]`) ; les anomalies rencontrées sont à noter directement sous l'item concerné.

## Environnement

| | |
|---|---|
| Frontend | `http://localhost:5174` |
| API (doc interactive) | `http://localhost:8000/api/v1/docs` (ou le port du backend actif) |
| E-mails de test (Mailpit) | `http://localhost:8025` — tous les e-mails envoyés par la plateforme (activation, réinitialisation, notifications) atterrissent ici, jamais dans une vraie boîte |
| Mot de passe commun | `demo-greenfinance-2026` |

### Comptes

| Rôle | E-mail | Entreprise rattachée |
|---|---|---|
| ADMIN | `admin@greenfinance-demo.com` | — |
| AUDITOR | `auditeur@greenfinance-demo.com` | — |
| INVESTOR | `investisseur@greenfinance-demo.com` | — |
| INSTITUTION | `institution@greenfinance-demo.com` | — |
| RESEARCHER | `chercheur@greenfinance-demo.com` | — |
| ENTERPRISE | `atlas@greenfinance-demo.com` | Atlas Industries |
| ENTERPRISE | `verdance@greenfinance-demo.com` | Verdance Foods |
| ENTERPRISE | `nordwind@greenfinance-demo.com` | Nordwind Energie |
| ENTERPRISE | `meridian@greenfinance-demo.com` | Meridian Mining |
| ENTERPRISE | `bluehorizon@greenfinance-demo.com` | Blue Horizon Shipping |
| ENTERPRISE | `ferrosahel@greenfinance-demo.com` | Ferrosahel Mining |

### État des rapports au démarrage des tests

| Entreprise | Rapports | Publiée ? |
|---|---|---|
| Atlas Industries | 2025 **VALIDÉ** (score affiché) + 2026 **BROUILLON** (correction en cours) | Oui |
| Nordwind Energie | 2025 **VALIDÉ** | Oui |
| Blue Horizon Shipping | 2025 **VALIDÉ** + 2026 **EN AUDIT** (affecté il y a 15 j — en retard) | Oui |
| Ferrosahel Mining | 2026 **VALIDÉ** + 2027 **À AFFECTER** (non affecté) | Oui |
| Meridian Mining | 2025 **EN ATTENTE DE DÉCISION** (avis d'audit rendu) | Non |
| Verdance Foods | 2025 **VALIDÉ**, score 77,1/100 | **Non — publiable** |

Portefeuille investisseur « Transition climat 2026 » (4 positions). Projet de recherche
« Intensité carbone des industries lourdes » (1 chercheur affecté, 4 entreprises en périmètre).
Analyse « Mines et industrie : premières comparaisons » (**SOUMISE**, en attente de décision
Institution).

### Lacunes connues (à garder en tête, pas des bugs)

- **Aucun ISIN/LEI/ticker** renseigné sur les 6 entreprises → bloque le test réel de
  l'import de positions par identifiant et de la validation croisée par rapprochement (sections
  dédiées plus bas, avec le format CSV attendu si tu veux les tester quand même avec tes propres
  identifiants).
- **Aucune demande d'accès ni compte en attente d'activation** → les sous-listes correspondantes
  de `Admin → Utilisateurs` seront vides tant qu'une inscription publique n'a pas été faite dans ce
  run de test (section Parcours public, qui en crée une).
- **Dépôt d'un nouveau rapport (Entreprise → nouvelle déclaration)** : lors de la préparation des
  données de démo, le worker d'extraction (Docling) a crashé silencieusement sur deux dépôts de
  test, sans trace d'erreur exploitable. Si ce test reste bloqué en « Analyse en cours » plus de
  quelques minutes, c'est probablement ce bug plutôt qu'une erreur de manipulation — à signaler.

---

## Parcours public (sans session)

- [ ] **Connexion** (`/login`) — mauvais mot de passe → message générique, pas de fuite sur
      l'existence du compte. Bon mot de passe → redirection vers l'espace du rôle.
- [ ] **Inscription entreprise** (`/inscription/entreprise`) — formulaire complet + lettre de
      mandat (PDF) → e-mail de confirmation dans Mailpit avec un code → saisie du code → demande
      créée, visible ensuite dans `Admin → Utilisateurs → Demandes d'accès`.
- [ ] **Suivi d'inscription** (`/inscription-entreprise/suivi?token=...`, lien reçu par e-mail) —
      affiche le statut (en attente / infos demandées / acceptée / rejetée) sans connexion.
- [ ] **Inscription investisseur / chercheur** (`/inscription/investisseur`,
      `/inscription/chercheur`) — demande d'accès avec organisation/domaine de recherche.
- [ ] **Mot de passe oublié** (`/mot-de-passe-oublie`) — e-mail avec lien à usage unique dans
      Mailpit → nouveau mot de passe → connexion avec le nouveau.
- [ ] **Lien expiré/déjà utilisé** — réutiliser un lien de réinitialisation déjà consommé → erreur
      claire, pas de 500.
- [ ] **Contact** (`/contact`) — formulaire envoyé → reçu dans Mailpit (`CONTACT_TO_EMAIL`).
- [ ] **Accès refusé** — tenter une URL d'un autre rôle en étant connecté (ex. `/admin` connecté en
      Investisseur) → 403 côté API, redirection ou message clair côté UI.
- [ ] **Ressource d'un autre tenant** — en Entreprise, appeler l'URL d'un rapport d'une AUTRE
      entreprise → 404 (jamais un 403 qui confirmerait l'existence du rapport).

---

## Espace Administrateur (`admin@greenfinance-demo.com`)

- [ ] **Tableau de bord** (`/admin`) — compteurs cohérents avec l'état ci-dessus (rapports à
      affecter, en retard, en attente de décision, à republier).
- [ ] **Utilisateurs** (`/admin/utilisateurs`) — onglets Demandes d'accès / Comptes en attente
      d'activation / Tous les utilisateurs ; valider une demande d'accès créée dans le parcours
      public → compte provisionné, e-mail d'activation dans Mailpit.
- [ ] **Entreprises → Entreprises inscrites** (`/admin/entreprises?onglet=inscrites`) — recherche
      par nom/secteur/pays.
- [ ] **Entreprises → Publiables** (`?onglet=publiables`) — Verdance Foods listée → **Publier** →
      elle devient visible côté Investisseur/Chercheur/Institution, disparaît de cette liste.
- [ ] **Entreprises → À republier** (`?onglet=a-republier`) — vide actuellement ; pour la garnir :
      corriger puis revalider un rapport d'une entreprise déjà publiée (ex. le brouillon 2026
      d'Atlas) → elle doit apparaître ici.
- [ ] **Entreprises → Scores ESG** (`?onglet=scores`) — liste des scores officiels calculés.
- [ ] **Fiche entreprise** (`/admin/entreprises/:id`) — profil, logo (upload/suppression), KYC
      (vérification LEI live si renseigné), suspendre → l'entreprise ne peut plus déposer →
      réactiver.
- [ ] **Rapports d'une entreprise** (`/admin/entreprises/:id/rapports`).
- [ ] **Rapports → Tous** (`/admin/rapports?onglet=tous`) — pagination, filtre par statut.
- [ ] **Rapports → Alertes** (`?onglet=alertes`) — Blue Horizon Shipping listée en « audit en
      retard » → **Voir** ouvre le dossier.
- [ ] **Rapports → À affecter** (`?onglet=a-affecter`) — Ferrosahel Mining → choisir
      `auditeur@greenfinance-demo.com` dans le sélecteur → **Affecter** → bascule en IN_AUDIT,
      disparaît de la liste, apparaît dans le dossier de l'Auditeur.
- [ ] **Rapports → En attente de décision** (`?onglet=en-validation`) — Meridian Mining →
      **Décider**.
- [ ] **Détail d'un rapport** (`/admin/rapports/:id`) — sur Meridian (PENDING_DECISION) :
      indicateurs + page-preuve de chacun, avis d'audit, données financières (CA/EVIC, requis pour
      PCAF), historique des versions, puis **Valider** (calcule le score dans la même transaction),
      **Rejeter** et **Demander une correction** (sur une copie si tu veux garder l'état pour
      quelqu'un d'autre).
- [ ] **Relance d'extraction** — sur un rapport `EXTRACTION_FAILED` (aucun actuellement ; si le bug
      Docling ci-dessus en produit un, le tester ici) → **Relancer**.
- [ ] **Auditeurs** (`/admin/auditeurs`) — charge de travail par auditeur.
- [ ] **Portefeuilles** (`/admin/portefeuilles`) — lecture seule, « Transition climat 2026 »
      visible.
- [ ] **Analyses** (`/admin/analyses`) — filtre par statut, l'analyse SOUMISE visible.
- [ ] **Projets** (`/admin/projets`) — « Intensité carbone des industries lourdes » visible.
- [ ] **Journal d'audit** (`/admin/journal-audit?concerne=...`) — filtrable par action/ressource ;
      les connexions de ce run de test doivent y apparaître en temps réel.
- [ ] **Profil** (`/admin/profil`) — changement de mot de passe, avatar, MFA si activé.

---

## Espace Entreprise

Teste avec `atlas@` (historique riche) **et** `meridian@` (dossier en attente de décision, pour
voir la vue entreprise d'un rapport pas encore décidé).

- [ ] **Tableau de bord** (`/company`) — session en cours + dernier score officiel.
- [ ] **Déclarations** (`/company/declarations`) — historique ; sur Atlas, le brouillon 2026 doit
      afficher un stepper différent de l'historique des rapports clos.
- [ ] **Détail d'une déclaration validée** (`/company/declarations/:id`, rapport 2025 d'Atlas) —
      score affiché, indicateurs avec preuve, téléchargement de la synthèse PDF.
- [ ] **Brouillon en cours** (`/company/declarations/:id`, rapport 2026 d'Atlas) — édition des
      valeurs, dépôt du fichier, **Soumettre** → verrouille (🔒), passe à `AWAITING_ASSIGNMENT`.
- [ ] **Dossier en attente de décision** (`/company/declarations/:id`, rapport de Meridian) — vue
      lecture seule, statut « En cours d'examen 🔒 ».
- [ ] **Nouvelle déclaration** — sur une entreprise sans déclaration active (ex. `nordwind@`) :
      **Nouvelle déclaration** → dépôt direct d'un PDF → `EXTRACTING` → attendre l'issue (voir la
      lacune connue sur le worker Docling ci-dessus).
- [ ] **Import par URL** — alternative au dépôt de fichier, si l'option est présente dans l'UI.
- [ ] **Réponse à une correction demandée** — sur un rapport `REVISION_REQUESTED` (aucun
      actuellement ; en créer un via **Demander une correction** côté Admin pour tester ce chemin).
- [ ] **Profil** (`/company/profile`) — identité, ISIN/LEI/ticker (utile pour débloquer les tests
      investisseur plus bas), montant minimum d'investissement.

---

## Espace Auditeur (`auditeur@greenfinance-demo.com`)

- [ ] **Dossiers affectés** (`/audit`) — Blue Horizon Shipping (2026) y figure après l'affectation
      faite côté Admin.
- [ ] **Revue d'un dossier** (`/audit/rapports/:id`, Blue Horizon 2026) — 3 volets (liste des
      valeurs / extrait PDF / décision) ; pour chaque valeur : **Accepter**, **Corriger** (exige une
      nouvelle valeur + motif), **Non trouvée** (exige un motif) ; raccourcis clavier `A`/`E`/`N`,
      `J`/`K` pour naviguer.
- [ ] **Rendre l'avis** — bloqué tant que toutes les valeurs ne sont pas revues (message explicite
      « X valeur(s) restent à revoir ») ; une fois complet, avis Favorable / Favorable avec réserves
      / Correction requise / Défavorable (commentaire obligatoire sauf Favorable) → rapport passe en
      `PENDING_DECISION`, disparaît de « Dossiers affectés ».
- [ ] **Pré-score** — visible seulement après l'avis rendu (si exposé dans l'UI), jamais avant.
- [ ] **Historique** (`/audit/historique`) — les 6 avis déjà rendus (5 initiaux + celui de Verdance
      rendu pendant la préparation des données).
- [ ] **Profil** (`/audit/profil`).

---

## Espace Investisseur (`investisseur@greenfinance-demo.com`)

- [ ] **Tableau de bord** (`/investor`).
- [ ] **Catalogue** (`/investor/entreprises`) — les 5 entreprises publiées (4 initiales + Verdance
      une fois publiée côté Admin) ; filtre/recherche.
- [ ] **Fiche entreprise** (`/investor/entreprises/:id`) — score global + décomposition E/S/G face
      à la référence sectorielle, indicateurs avec preuve, émissions carbone par scope.
- [ ] **Comparaison** (`/investor/comparaison` → `/investor/comparaison/resultats?ids=...`) —
      sélectionner 2 à 4 entreprises publiées → tableau comparatif.
- [ ] **Portefeuilles** (`/investor/portefeuilles`) — « Transition climat 2026 », **Créer un
      portefeuille**.
- [ ] **Détail d'un portefeuille** (`/investor/portefeuilles/:id`) — montant total, score ESG
      agrégé, empreinte carbone PCAF (émissions financées Scopes 1+2, Scope 3 à part, WACI, qualité
      des données), **Exporter (CSV)**, **Renommer**, **Archiver**.
- [ ] **Ajouter une position** — manuellement (choisir une entreprise publiée, montant ou poids).
- [ ] **Fermer une position** — sur une position active, vérifier que **Modifier/Supprimer** ne sont
      proposés que pour une position encore planifiée, jamais sur une position déjà active.
- [ ] **Import CSV de positions** ⚠️ *nécessite un ISIN valide ou un ticker renseigné sur une
      entreprise (lacune connue ci-dessus)* — colonnes attendues :
      `identifier,identifier_type,outstanding_amount,currency,weight` (soit
      `outstanding_amount`+`currency`, soit `weight`, jamais les deux) :
      ```csv
      identifier,identifier_type,outstanding_amount,currency
      FR0000120271,ISIN,500000,EUR
      ```
- [ ] **Multi-devises** — ajouter une position dans une devise différente de la devise de référence
      du portefeuille → conversion à taux figé visible.
- [ ] **Profil** (`/investor/profil`).

---

## Espace Institution (`institution@greenfinance-demo.com`)

- [ ] **Tableau de bord** (`/institution`).
- [ ] **Entreprises** (`/institution/entreprises`, `/:id`) — même catalogue/fiche que l'Investisseur.
- [ ] **Chercheurs** (`/institution/chercheurs`) — `chercheur@` déjà rattaché (statut ACCEPTÉ) ;
      **Inviter un chercheur** avec une nouvelle adresse → e-mail d'invitation dans Mailpit.
- [ ] **Projets** (`/institution/projets`) — « Intensité carbone des industries lourdes » ;
      **Créer un projet**.
- [ ] **Détail d'un projet** (`/institution/projets/:id`) — périmètre (4 entreprises), chercheurs
      affectés, documents partagés ; **Ajouter une entreprise au périmètre**, **Affecter un
      chercheur**, **Téléverser un document**.
- [ ] **Analyses** (`/institution/analyses`) — l'analyse SOUMISE y figure.
- [ ] **Détail d'une analyse soumise** (`/institution/analyses/:id`) — **Valider** → statut VALIDÉE,
      ou **Demander une correction** (commentaire requis) → repasse en brouillon chercheur.
- [ ] **Export** — quota d'export (`export_quota`) visible/décompté si la fonctionnalité est
      exposée dans l'UI.
- [ ] **Profil** (`/institution/profil`).

---

## Espace Chercheur (`chercheur@greenfinance-demo.com`)

- [ ] **Tableau de bord** (`/researcher`).
- [ ] **Données** (`/researcher/entreprises`, `/:id`) — catalogue limité au périmètre des projets
      affectés.
- [ ] **Comparaison** (`/researcher/comparaison?ids=...`).
- [ ] **Mes projets** (`/researcher/projets`, `/:id`) — « Intensité carbone des industries lourdes »,
      lecture du périmètre et des documents partagés par l'Institution.
- [ ] **Analyses** (`/researcher/analyses`) — l'analyse SOUMISE (lecture seule tant qu'elle n'est
      pas renvoyée en correction) ; **Nouvelle analyse** → brouillon éditable → **Soumettre**.
- [ ] **Historique de versions d'une analyse** — après une correction demandée par l'Institution,
      vérifier que l'ancienne version reste consultable.
- [ ] **Export CSV** — quota limité, vérifier le message une fois épuisé.
- [ ] **Validation croisée** (`/researcher/validation-croisee`) ⚠️ *aucun jeu de référence importé
      actuellement — section vide par défaut*. Colonnes attendues (casse ignorée) : `isin` ou `lei`,
      `name`/`company_name`, et au moins une colonne de score parmi
      `environmental,social,governance,total` (échelle 0–100) :
      ```csv
      isin,name,environmental,social,governance,total
      FR0000120271,Atlas Industries,70,55,60,62
      ```
      *Nécessite un ISIN/LEI réel sur l'entreprise ciblée (même lacune que l'import portefeuille) —
      sans quoi toutes les lignes sont écartées comme non rapprochées.* Une fois importé : corrélation
      de Spearman + écart absolu moyen face aux scores officiels de la plateforme.
- [ ] **Rattachements** (`/researcher/rattachements`) — accepter/refuser une invitation
      d'institution.
- [ ] **Profil** (`/researcher/profil`).

---

## Règles transverses à vérifier au fil des tests

- [ ] **403 vs 404** — un rôle non autorisé reçoit 403 ; le bon rôle sur une ressource hors
      périmètre reçoit 404 (jamais de distinction qui confirmerait l'existence de la ressource).
- [ ] **Cookie de session** — `httpOnly`, disparaît à la déconnexion ; une session expirée redirige
      vers `/login` puis ramène sur la page quittée après reconnexion.
- [ ] **CSRF** — une requête mutante sans `X-CSRF-Token` (ou avec une mauvaise `Origin`) est rejetée.
- [ ] **Limite de tentatives** — plusieurs échecs de connexion rapprochés sur le même e-mail/IP →
      429 après un certain seuil.
- [ ] **Notifications in-app** — la cloche se met à jour après une action qui en déclenche une
      (ex. rapport affecté, avis rendu, entreprise publiée).
- [ ] **Changement d'e-mail / mot de passe** — lien à usage unique dans Mailpit, ancien lien
      invalidé après usage.

---

## Après les tests

Pense à redémonter l'infrastructure de test temporaire (backend dédié + worker + proxy Vite) si tu
n'en as plus besoin, ou dis-le-moi pour que je le fasse.
