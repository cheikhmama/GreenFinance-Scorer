# GreenFinance-Scorer — Analyse du projet pour la production ultérieure des diagrammes UML

> Ce document ne contient **aucun diagramme** (pas de Mermaid, pas de PlantUML, pas d'image). Il
> contient uniquement les données vérifiées nécessaires pour qu'un autre agent puisse produire,
> dans une étape séparée : les workflows (existant / proposé), le diagramme de classes, les cas
> d'utilisation (général et détaillés), 3 diagrammes de séquence, les diagrammes d'activité,
> l'architecture, les composants et le déploiement.

## Note méthodologique (couvre les points 1 et 2 de la consigne)

**Méthode.** Ce document est le produit de six passes de recherche indépendantes, chacune ayant lu
le code source **en intégralité** (pas des extraits) sur un périmètre du projet :

1. Modèles de données et schéma SQL (`app/**/models.py`, `app/core/enums.py`, migrations Alembic).
2. `app/auth`, `app/admin`, `app/company`, `app/access_requests`, `app/contact`.
3. `app/reporting`, `app/ingestion`, `app/audit`, `app/scoring`, `app/explainability`, `app/carbon`.
4. `app/investor`, `app/institution`, `app/researcher`.
5. Infrastructure : `app/worker`, `app/core/config.py`, Docker, CI, `pyproject.toml`.
6. Frontend (`frontend/src`) : routes, navigation, client API généré, workflows UI.

**Règle appliquée : rien n'est inventé.** Chaque affirmation ci-dessous est traçable à un fichier
et, le plus souvent, une ligne précise (`fichier:ligne`). Le projet contient deux documents cibles
— [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) et [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) —
explicitement marqués **« PROPOSED TARGET »**. Ils n'ont été utilisés que comme hypothèses de
travail ; chaque affirmation qu'ils contiennent a été **re-vérifiée indépendamment dans le code**.
Résultat global de cette vérification : une très large majorité de ce que ces documents décrivent
comme « cible » est **déjà implémenté**, souvent à l'identique (y compris les valeurs numériques
exactes). Les écarts réels trouvés (code ≠ doc, ou doc obsolète) sont listés section 17 — ils ne
sont jamais résolus par une supposition, uniquement signalés.

Quand une information n'a pas pu être confirmée avec certitude, elle est explicitement marquée
**« non confirmé »** ou **« ambigu, à confirmer »** plutôt que présentée comme un fait.

---

## 3. Présentation générale du système

**Nom du projet :** GreenFinance-Scorer.

**Objectif général.** Plateforme de notation ESG (Environnement/Social/Gouvernance) et carbone
pour des entreprises, destinée à être consultée par des investisseurs et des chercheurs. Chaque
valeur chiffrée affichée est rattachée à la page du rapport source qui la prouve (garantie « aucune
valeur sans preuve », vérifiée dans le pipeline d'extraction, section 7.4).

**Problème traité.** Remplacer une évaluation ESG déclarative et non vérifiable par un score
reproductible, décomposable indicateur par indicateur, et appuyé sur une preuve documentaire
consultable — avec une chaîne de responsabilité claire (entreprise → auditeur → administrateur)
avant toute publication.

**Principe de fonctionnement (vue d'ensemble, détaillé section 7).**
1. Une entreprise s'inscrit publiquement (lettre de mandat + vérification d'e-mail), un
   administrateur l'intègre (onboarding + contrôles KYC informatifs).
2. L'entreprise dépose un rapport PDF. Une extraction automatique (OCR + recherche sémantique +
   LLM) en tire les indicateurs ESG et carbone, chacun avec sa page de preuve.
3. Un auditeur affecté par l'administrateur revoit chaque valeur extraite et rend un avis.
4. L'administrateur décide (valider / rejeter / demander une correction). La validation calcule le
   score **dans la même transaction** que le changement de statut, avec une méthodologie figée par
   empreinte SHA-256.
5. Une fois publiée, l'entreprise devient visible des investisseurs (catalogue, comparaison,
   portefeuilles, empreinte carbone PCAF) et des chercheurs (analyses encadrées par une
   institution, validation croisée contre des jeux de données externes).

**Utilisateurs (rôles système, `app/core/enums.py:193-201`) :** `ADMIN`, `ENTERPRISE`, `AUDITOR`,
`INVESTOR`, `RESEARCHER`, `INSTITUTION` — six valeurs, aucune hiérarchie entre elles (un
utilisateur a exactement un rôle, colonne unique `User.role`). S'y ajoute un acteur non authentifié
(« Public ») qui déclenche l'inscription entreprise, la demande d'accès investisseur/chercheur, le
suivi de dossier et le formulaire de contact.

**Principaux domaines fonctionnels (un module backend par domaine, `app/<module>/`) :** compte et
session (`auth`), inscription/gouvernance entreprise (`company`, `admin`), demandes d'accès
(`access_requests`), contact (`contact`), cycle de vie du rapport (`reporting`), extraction
documentaire (`ingestion`, module interne sans API propre), audit (`audit`), calcul du score
(`scoring`, module interne), explicabilité (`explainability`), carbone/PCAF (`carbon`, module
interne), espace investisseur (`investor`), gouvernance de recherche (`institution`), espace
chercheur (`researcher`), traitement asynchrone (`worker`).

**Grandes étapes du fonctionnement global** (détaillées section 7) : inscription & onboarding →
dépôt & extraction du rapport → audit → décision & score → publication → consultation/analyse par
investisseurs et chercheurs.

---

## 4. Acteurs et rôles

### 4.0 Acteur « Public » (non authentifié)

- **Responsabilités** : déclencheur des parcours d'entrée dans le système.
- **Fonctionnalités accessibles** : inscription d'entreprise (`POST /companies/register`),
  vérification d'e-mail (`POST /companies/registration/verify-email`), suivi de dossier par jeton
  (`POST /companies/registration-status[/reply]`), demande d'accès Investisseur/Chercheur
  (`POST /access-requests`), formulaire de contact (`POST /contact`), confirmation de changement
  d'e-mail et réinitialisation de mot de passe (liens reçus par e-mail).
- **Données consultées** : uniquement l'état de sa propre demande (via jeton à usage de suivi,
  jamais par identifiant devinable).
- **Restrictions** : aucune information sur l'existence d'un e-mail/ISIN/LEI/compte n'est jamais
  révélée (réponse `202` uniforme quel que soit le résultat réel —
  `app/company/registration.py:258-351`, `app/access_requests/service.py:97-179`) ; limites de
  débit par IP partout (3/heure sur l'inscription, les réponses à une demande d'info et les
  demandes d'accès — `app/company/registration.py:65-66`, `app/access_requests/service.py:28`).

### 4.1 ADMIN — Administrateur de la plateforme

- **Rôle** : supervision complète ; seul rôle à voir « tout » (règle du `README.md:70`, confirmée
  par l'absence de restriction de périmètre sur ses routes, `app/admin/router.py`).
- **Responsabilités** : onboarding et KYC des entreprises, gestion des comptes (tous rôles sauf
  création d'autres `ADMIN`, bloquée explicitement — `app/admin/utilisateurs.py:124-128`),
  affectation des auditeurs, décision finale sur les rapports (valider/rejeter/demander
  correction), publication/suspension des entreprises, saisie des données financières PCAF
  (chiffre d'affaires, valeur d'entreprise), consultation du journal d'audit, tableaux de bord.
- **Données qu'il peut consulter** : toutes (utilisateurs, rapports à tout statut, entreprises à
  tout statut, portefeuilles de tous les investisseurs, analyses de tous les chercheurs, projets de
  toutes les institutions — ces trois derniers en lecture seule, `app/admin/router.py:1102-1212`).
- **Données qu'il peut modifier** : comptes utilisateurs, profil entreprise (remplacement complet),
  identifiants (ISIN/LEI/ticker), logo, statut d'inscription/de publication, décision de rapport,
  financiers PCAF par rapport, configuration de scoring de référence (indirectement, via le
  fichier YAML — pas d'endpoint d'édition en ligne constaté).
- **Ne peut pas** : écrire dans le journal de revue d'un auditeur (`metric_reviews` — lecture
  seule, `app/admin/router.py:553-566`) ; voir le brouillon d'une analyse de chercheur non soumise
  (ce périmètre appartient à l'institution, pas à l'admin, qui n'a d'ailleurs pas de route dédiée
  à ce niveau de détail).
- **Relations avec les autres acteurs** : affecte les Auditeurs aux rapports ; décide du sort des
  Entreprises ; active les comptes Investisseur/Chercheur/Institution après leur demande d'accès.

### 4.2 ENTERPRISE — Entreprise déclarante

- **Rôle** : propriétaire d'une fiche `Company` (lien `owner_user_id`) ; dépose ses propres
  rapports de durabilité.
- **Responsabilités** : s'inscrire (si public) ou utiliser le compte provisionné par l'admin,
  déposer/corriger ses rapports ESG, suivre leur statut, télécharger la synthèse PDF, répondre à
  une demande d'information lors de l'onboarding.
- **Données consultées** : son propre profil, ses propres rapports (à tout statut), sa propre
  vérification LEI en direct (GLEIF).
- **Données modifiables** : ses rapports en brouillon (fichier, soumission, suppression), son nom
  de compte, son e-mail (avec confirmation), son mot de passe, son avatar.
- **Restrictions** : ne voit **jamais** les statuts internes détaillés du rapport — l'UI fusionne
  `EXTRACTING`/`AWAITING_ASSIGNMENT`/`IN_AUDIT`/`PENDING_DECISION` en un seul état affiché
  (confirmé côté frontend, `research_frontend.md` — `CompanyReportDetailPage`) ; ne voit jamais les
  avis d'audit ni les valeurs auditées avant validation ; ne peut déposer que si sa société est
  `ACTIVE` (`app/company/rapports.py:89-103`).
- **Relations** : son rapport est examiné par un Auditeur affecté par l'Admin, puis décidé par
  l'Admin ; une fois publiée, sa fiche devient visible des Investisseurs/Chercheurs.

### 4.3 AUDITOR — Auditeur

- **Rôle** : vérificateur indépendant, affecté rapport par rapport par l'Admin (`auditor_id` sur
  `ESGReport`).
- **Responsabilités** : examiner chaque indicateur/donnée carbone extrait et sa preuve, décider
  pour chacun ACCEPTED/OVERRIDDEN(avec nouvelle valeur)/NOT_FOUND, puis rendre un avis global
  (`FAVORABLE`/`FAVORABLE_WITH_RESERVATIONS`/`CORRECTION_REQUIRED`/`UNFAVORABLE`).
- **Données consultées** : uniquement les dossiers qui lui sont affectés (`app/audit/router.py` —
  toute tentative sur un rapport d'un autre auditeur renvoie `404`, jamais `403`, pour ne pas
  révéler l'existence du rapport — `app/audit/opinion.py:42-43`) ; un « pré-score » non officiel,
  visible **seulement après** avoir rendu son avis (`app/audit/revue.py:120-143`).
- **Données modifiables** : le statut de revue de chaque valeur (`metric_reviews`, **jamais** la
  valeur brute extraite elle-même) et son avis d'audit.
- **Restrictions** : ne peut rendre un avis que si **toutes** les valeurs du rapport ont été
  revues (`422 revue_incomplete` sinon — `app/audit/opinion.py:49-56`) ; l'avis clôt la revue (plus
  aucune modification possible après) ; le journal `metric_reviews` est strictement append-only, y
  compris pour lui-même (déclencheur PostgreSQL, section 8.5).
- **Relations** : reçoit ses dossiers de l'Admin ; son avis conditionne la décision de l'Admin.

### 4.4 INVESTOR — Investisseur

- **Rôle** : consommateur des données publiées, gestionnaire de portefeuilles.
- **Responsabilités** : consulter/comparer les entreprises publiées, gérer des portefeuilles
  (positions, import CSV/JSON, export), consulter l'empreinte carbone PCAF agrégée.
- **Données consultées** : catalogue des entreprises **publiées uniquement**
  (`Company.published_at IS NOT NULL`), comparaison jusqu'à 4 entreprises
  (`app/investor/entreprises.py:270-287`), ses propres portefeuilles et positions.
- **Données modifiables** : ses portefeuilles (créer/renommer/archiver/restaurer/supprimer s'il
  n'a jamais eu de position), ses positions (ajouter/modifier si `PLANIFIEE`/fermer si
  `OUVERTE`/supprimer si `PLANIFIEE`), import de positions (une seule fois, sur portefeuille vide).
- **Restrictions** : ne voit jamais une entreprise non publiée (même par identifiant deviné —
  mêmes codes d'erreur qu'une entreprise inexistante) ; import strictement tout-ou-rien ; devise de
  référence du portefeuille figée à l'USD à la création.
- **Relations** : aucune relation directe avec les autres rôles — lecture seule des données
  produites en amont (Entreprise → Auditeur → Admin).

### 4.5 RESEARCHER — Chercheur

- **Rôle** : analyste, encadré par une ou plusieurs Institutions (table de liaison
  `ResearcherAffiliation`, puis `ProjectAssignment` par projet).
- **Responsabilités** : accepter/refuser les invitations d'institutions, rédiger des analyses
  comparatives au sein d'un projet, les soumettre, les corriger si demandé, importer des jeux de
  données externes et lancer une validation croisée (corrélation de Spearman).
- **Données consultées** : uniquement les entreprises dans le périmètre **cumulé de tous ses
  projets affectés** (`entreprises_perimetre_chercheur`) — jamais le catalogue complet, à la
  différence de l'Investisseur.
- **Données modifiables** : ses propres analyses (tant que `BROUILLON`), ses propres jeux de
  données de référence (privés, jamais partagés, jamais écrits sur les données de la plateforme).
- **Restrictions** : ne peut créer une analyse que sur un projet auquel il est **affecté** (et pas
  seulement « rattaché » à l'institution — deux niveaux distincts, section 7.8) ; aucun quota
  d'export CSV constaté côté chercheur (le quota existe uniquement côté Institution, section 6.3
  du rapport de recherche investisseur/institution/chercheur) ; aucune limite au nombre de
  brouillons simultanés constatée.
- **Relations** : reçoit des invitations et des décisions (valider/corriger) d'une Institution.

### 4.6 INSTITUTION — Institution de recherche

- **Rôle** : superviseur de la recherche, titulaire d'un quota d'export (`InstitutionProfile`).
- **Responsabilités** : inviter des chercheurs, créer/clôturer des projets, définir leur périmètre
  (entreprises publiées + documents = rapports publiés de ces entreprises), affecter des chercheurs
  acceptés à un projet, décider des analyses soumises (valider/demander correction), les exporter.
- **Données consultées** : catalogue complet des entreprises publiées (pour composer un périmètre
  — **non filtré**, volontairement, `app/institution/projets.py:176-178`) ; mais le détail d'une
  entreprise/preuve n'est accessible que si elle est dans le périmètre **cumulé de ses propres
  projets** ; les analyses soumises de ses projets (jamais les brouillons).
- **Données modifiables** : ses projets (création, clôture — pas de modification des dates après
  création), leur périmètre et leurs documents, les décisions sur les analyses soumises.
- **Restrictions** : ne peut affecter qu'un chercheur ayant **accepté** son invitation
  (`ResearcherAffiliation.status == ACCEPTE`) ; ne peut ajouter au périmètre qu'une entreprise déjà
  publiée ; ne peut attacher que le rapport **actuellement publié** d'une entreprise du périmètre
  (jamais un rapport supplanté par une publication plus récente) ; export limité par un quota fini,
  jamais réapprovisionné dans le périmètre lu.
- **Relations** : invite et encadre des Chercheurs ; ses décisions déclenchent des notifications
  vers le Chercheur concerné.

---

## 5. Fonctionnalités du système (par module)

Les tableaux ci-dessous regroupent les fonctionnalités réellement implémentées. Les endpoints
complets (avec file:line) sont disponibles dans les rapports de recherche sources ; ce document ne
reprend que ce qui est nécessaire à la compréhension fonctionnelle et aux futurs diagrammes.

### 5.1 Compte et session (`app/auth`)

| Fonctionnalité | Acteur | Objectif | Précondition | Résultat |
|---|---|---|---|---|
| Connexion | tous rôles | Ouvrir une session | compte actif, mot de passe défini | cookies `__Host-access_token` (JWT 12h) + `__Host-csrf_token` |
| Déconnexion | tous | Fermer toutes ses sessions | authentifié | compteur de génération Redis incrémenté (révocation immédiate) |
| Mot de passe oublié / réinitialisation | public puis titulaire | Reprendre l'accès à un compte | jeton e-mail valide 30 min | nouveau mot de passe (≥12 car., ≤72 octets) |
| Activation de compte | titulaire (lien e-mail) | Définir le mot de passe initial et ouvrir la session | jeton d'activation valide 72h, usage unique | compte activé, session ouverte directement |
| Changement d'e-mail | titulaire | Modifier son adresse | mot de passe courant si l'e-mail change réellement | confirmation par lien envoyé à la **nouvelle** adresse, 24h |
| Avatar | titulaire | Illustrer son profil | fichier ≤2 Mo, signature réelle PNG/JPEG/WEBP | fichier stocké, servi à tout utilisateur authentifié (voir §17) |
| Vérification de mot de passe / changement | titulaire | Confirmer son identité avant une action sensible | mot de passe courant correct | 204 ou nouvelles sessions |

### 5.2 Inscription et gouvernance entreprise (`app/company`, `app/admin`)

| Fonctionnalité | Acteur | Objectif | Entrée clé | Règle métier | Résultat |
|---|---|---|---|---|---|
| Inscription publique | Public | Créer une demande d'inscription | identité légale, identifiant fiscal par pays, ISIN/LEI optionnels, e-mail professionnel, lettre de mandat PDF ≤5 Mo | pas de webmail public ; e-mail doit correspondre au domaine du site si fourni ; 3/IP/heure ; champ piège vide | statut `EMAIL_VERIFICATION_PENDING`, code à 6 chiffres envoyé |
| Vérification d'e-mail | Public | Confirmer l'adresse | code reçu | 30 min, 5 tentatives, 20 vérifications/IP/h | statut `PENDING_ONBOARDING`, jeton de suivi émis |
| Suivi de dossier | Public (par jeton) | Consulter l'état de sa demande | jeton | — | vue du statut, du motif de rejet ou de la demande d'info |
| Réponse à une demande d'info | Public (par jeton) | Compléter le dossier | nouveau mandat + message ≤2000 car. | seulement si `INFO_REQUESTED` | retour à `PENDING_ONBOARDING` |
| Décision d'onboarding | ADMIN | Approuver / rejeter / demander une info | motif requis pour rejet/demande | verrou de ligne, uniquement depuis `PENDING_ONBOARDING`/`INFO_REQUESTED` | `ACTIVE` (+lien d'activation 72h) / `REJECTED` (compte désactivé, dossier conservé) / `INFO_REQUESTED` (nouveau jeton) |
| Contrôle KYC | ADMIN | Éclairer la décision | — | 4 contrôles (GLEIF enregistrement, nom légal, domaine e-mail, mandat) — **n'empêche jamais** la décision | rapport `PASSED/FAILED/NOT_VERIFIABLE/NOT_APPLICABLE` par contrôle |
| Publication / suspension / réactivation | ADMIN | Rendre visible le score officiel | rapport validé existant (publication) | suspension bloque les nouvelles positions, pas les existantes | `published_at` mis à jour / `SUSPENDED` / `ACTIVE` |
| Gestion du profil entreprise | ADMIN | Compléter la fiche | — | remplacement complet (pas de patch partiel) | profil mis à jour |
| Vérification LEI en direct | ENTERPRISE | Auto-contrôle | LEI déclaré | appel GLEIF, jamais persisté | résultat affiché, jamais bloquant |

### 5.3 Demandes d'accès (`app/access_requests`)

| Fonctionnalité | Acteur | Objectif | Règle métier | Résultat |
|---|---|---|---|---|
| Demande d'accès | Public | Devenir Investisseur ou Chercheur | un seul de `investor_type`/`research_domain` selon le rôle ; 3/IP/h ; e-mail inconnu ou `REJECTED` réouvrable | compte créé sans mot de passe, statut `PENDING_APPROVAL` |
| Décision | ADMIN | Approuver/rejeter | motif requis au rejet | `APPROVED` (lien d'activation) / `REJECTED` (compte désactivé) |

### 5.4 Cycle de vie du rapport (`app/reporting`, `app/company/rapports.py`)

| Fonctionnalité | Acteur | Objectif | Règle métier | Résultat |
|---|---|---|---|---|
| Ouvrir une session de déclaration | ENTERPRISE (sa société `ACTIVE`) / ADMIN | Créer un brouillon pour un exercice | un seul brouillon/rapport non soumis par (société, exercice, type) ; exercice non déjà validé | `ESGReport` statut `DRAFT` |
| Joindre un fichier | ENTERPRISE / ADMIN | Lancer l'analyse | brouillon verrouillé, PDF valide, doublon détecté par somme de contrôle | statut `EXTRACTING`, job d'extraction enfilé |
| Dépôt en une étape | ENTERPRISE | Déposer et soumettre directement | même validations fichier | rapport créé **et** soumis immédiatement |
| Import par URL | ENTERPRISE / ADMIN | Déposer un PDF distant | protections anti-SSRF (IP publique uniquement, redirections revalidées, 50 Mo, 60 s) | comme un dépôt direct |
| Liste de complétude | tout rôle du périmètre | Savoir ce qui a été trouvé | — | compteurs trouvé/non trouvé/confirmé absent par groupe |
| Soumettre | ENTERPRISE / ADMIN | Verrouiller le brouillon analysé | fichier présent, analyse terminée sans erreur, société `ACTIVE` | `submitted_at` figé, statut `AWAITING_ASSIGNMENT` |
| Abandonner | ENTERPRISE / ADMIN | Supprimer un brouillon | statut `DRAFT` uniquement | ligne supprimée |
| Relancer une extraction | ADMIN | Reprendre après échec | statut `EXTRACTION_FAILED` | statut `EXTRACTING`, nouveau job |
| Affecter un auditeur | ADMIN | Démarrer l'audit | statut `AWAITING_ASSIGNMENT`, cible = AUDITOR actif | `auditor_id`, statut `IN_AUDIT` |
| Déposer une correction | ENTERPRISE | Répondre à une demande de correction | statut `REVISION_REQUESTED` | nouvelle version (`version+1`, `previous_report_id`) |

### 5.5 Audit (`app/audit`)

| Fonctionnalité | Acteur | Objectif | Règle métier | Résultat |
|---|---|---|---|---|
| Lister ses dossiers | AUDITOR | Voir sa file de travail | dossiers `IN_AUDIT` affectés à lui | liste |
| Revoir une valeur | AUDITOR (affecté) | Accepter/corriger/signaler absente | statut `IN_AUDIT` ; `OVERRIDDEN` exige une nouvelle valeur ; motif requis sauf `ACCEPTED` | ligne append-only `MetricReview` + mise à jour du mirroir sur la valeur |
| Rendre un avis | AUDITOR (affecté) | Clore la revue | toutes les valeurs revues (sinon 422) ; commentaire requis si non `FAVORABLE` | `AuditOpinion`, statut `PENDING_DECISION` |
| Pré-score | AUDITOR (affecté) | Avoir un ordre de grandeur non officiel | uniquement après l'avis | score calculé avec les valeurs auditées |
| Lecture du journal de revue | ADMIN | Contrôle | — | lecture seule, jamais d'écriture |

### 5.6 Décision et score officiel (`app/admin/review_queue.py`, `app/scoring`)

| Fonctionnalité | Acteur | Objectif | Règle métier | Résultat |
|---|---|---|---|---|
| Vérifier la « scorabilité » | ADMIN | Anticiper un blocage | — | couverture actuelle vs. minimum de la config |
| Valider | ADMIN | Publier un score officiel | statut `PENDING_DECISION`, verrou de ligne, avis existant, score calculable, couverture ≥ minimum (si fixé) | transaction atomique (détail §7.6) : `VALIDATED` + `Score` + dénormalisation sur le rapport |
| Rejeter | ADMIN | Clore sans score | statut `PENDING_DECISION` | `REJECTED` |
| Demander une correction | ADMIN | Renvoyer à l'entreprise | statut `PENDING_DECISION` | `REVISION_REQUESTED` |
| Recalculer un score manquant | ADMIN | Réparer un état incohérent | rapport `VALIDATED` sans `Score` | nouveau `Score` inséré |
| Explication du score | tout rôle autorisé sur le rapport | Comprendre la décomposition | rapport officiel (dernier validé d'une société publiée pour les rôles externes) | contributions par indicateur, base de référence secteur/univers |

### 5.7 Espace investisseur (`app/investor`)

| Fonctionnalité | Acteur | Objectif | Règle métier | Résultat |
|---|---|---|---|---|
| Catalogue / détail / comparaison | INVESTOR | Explorer les entreprises publiées | comparaison plafonnée à 4 | fiches avec score, carbone agrégé, montant minimum converti |
| Créer / gérer un portefeuille | INVESTOR | Organiser ses positions | devise de référence fixée à l'USD | CRUD portefeuille |
| Ajouter / modifier / fermer / supprimer une position | INVESTOR | Gérer ses lignes | modification/suppression seulement si `PLANIFIEE` ; fermeture seulement si `OUVERTE` ; montant minimum de l'entreprise respecté | position créée/mise à jour |
| Importer des positions (CSV/JSON) | INVESTOR | Charger un portefeuille entier | portefeuille vide et non archivé ; tout-ou-rien ; somme des poids ±0,001 si mode poids | positions créées, comptage matched/unmatched/ambiguous |
| Exporter en CSV | INVESTOR | Extraire ses données | — | fichier CSV |
| Empreinte carbone PCAF | INVESTOR | Évaluer l'impact climatique du portefeuille | seules les positions `ACTIVE` comptent ; Scope 3 jamais sommé aux Scopes 1+2 ; donnée manquante exclue, jamais comptée zéro | facteurs d'attribution, émissions financées, WACI, qualité de donnée, par position et agrégé |

### 5.8 Gouvernance de recherche — Institution (`app/institution`)

| Fonctionnalité | Acteur | Objectif | Règle métier | Résultat |
|---|---|---|---|---|
| Inviter un chercheur | INSTITUTION | Construire son équipe | une ligne par (chercheur, institution) ; réinvitation réutilise la ligne | `ResearcherAffiliation` `EN_ATTENTE` |
| Créer / clôturer un projet | INSTITUTION | Cadrer une recherche | cohérence des dates à la création | `Project` `OUVERT`/`CLOTURE` |
| Affecter un chercheur à un projet | INSTITUTION | Donner accès au périmètre | chercheur `ACCEPTE`, projet `OUVERT` | `ProjectAssignment` |
| Définir le périmètre (entreprises) | INSTITUTION | Délimiter l'accès aux données | entreprise déjà publiée | `ProjectCompany` |
| Attacher un document | INSTITUTION | Fournir le rapport source | rapport = rapport **actuellement publié** de l'entreprise, déjà dans le périmètre | `ProjectDocument` |
| Décider d'une analyse | INSTITUTION | Valider ou renvoyer | statut `SOUMISE` uniquement ; commentaire requis si correction | `VALIDEE`/`CORRECTION_DEMANDEE` |
| Exporter une analyse | INSTITUTION | Diffuser un résultat | quota d'export restant > 0 | CSV, quota décrémenté |

### 5.9 Espace chercheur (`app/researcher`)

| Fonctionnalité | Acteur | Objectif | Règle métier | Résultat |
|---|---|---|---|---|
| Répondre à une invitation | RESEARCHER | Accepter/refuser une institution | statut `EN_ATTENTE` uniquement | `ACCEPTE`/`REFUSE` |
| Rédiger une analyse | RESEARCHER | Produire un travail comparatif | affecté au projet, projet `OUVERT`, ≥1 entreprise du périmètre du projet, chaque entreprise publiée avec score officiel | `Analysis` `BROUILLON`, snapshot (`report_id`,`score_id`) figé par entreprise |
| Soumettre | RESEARCHER | Livrer à l'institution | `BROUILLON`, ≥1 entreprise liée | `SOUMISE` |
| Corriger après demande | RESEARCHER | Répondre à l'institution | statut `CORRECTION_DEMANDEE` | nouvelle version (`version+1`) |
| Importer un jeu de données externe | RESEARCHER | Préparer une validation croisée | CSV ≤5 Mo/20000 lignes ; au moins ISIN ou LEI + une colonne de score | `ReferenceDataset` + lignes, import **partiel** (lignes invalides ignorées, échec seulement si 0 ligne) |
| Validation croisée | RESEARCHER | Comparer à une référence externe | rapprochement ISIN puis LEI, limité au périmètre cumulé de ses projets | corrélation de Spearman + écart absolu moyen par pilier, liste des non-rapprochées avec motif |

---

## 6. Workflow du système existant (avant la solution)

**Constat, sans invention.** Aucun document du dépôt (code, `docs/`, `README.md`) ne décrit un
processus manuel ou un système préexistant que GreenFinance-Scorer remplacerait. Il s'agit d'un
projet construit directement comme plateforme numérique ; il n'y a pas de cahier des charges ni de
schéma de « processus métier existant » dans ce dépôt à partir duquel un workflow « avant » pourrait
être reconstruit fidèlement.

Pour ne rien inventer, ce document **ne fournit pas** d'étapes, d'acteurs, de données échangées ou
de lenteurs/doublons détaillés pour un « système existant », faute de source. La seule chose que
l'on peut rattacher au texte du projet lui-même est la *motivation* énoncée dans
`README.md:5-8` : remplacer une notation ESG où la preuve documentaire n'est pas rattachée à la
valeur, où l'audit et la validation ne sont pas formalisés, et où un score ancien ne se recalcule
pas forcément à l'identique. Ce sont des caractéristiques générales d'un problème à résoudre, pas
la description d'un système antérieur réellement documenté dans ce dépôt.

**Recommandation (à traiter en section 17 comme zone d'incertitude) :** si un diagramme du
« workflow système existant » est réellement requis pour le livrable final (rapport/soutenance),
il faut obtenir cette information **auprès des parties prenantes humaines** (porteur du projet,
cahier des charges externe au dépôt) plutôt que de la déduire du code. Ce document s'abstient
volontairement de produire cette section avec un contenu inventé.

---

## 7. Workflow du système proposé (= système actuellement implémenté)

Convention : **Acteur** = qui déclenche ; **Tx** = ce qui est commité ensemble dans une seule
transaction ; **Job** = travail asynchrone enfilé sur ARQ/Redis, exécuté par un worker après le
commit déclencheur. Les numéros d'étape citent `fichier:ligne` pour vérification.

### 7.1 Inscription et onboarding d'une entreprise

| # | Acteur | Action | Entrée | Traitement / validation | Sortie / changement d'état | Job |
|---|---|---|---|---|---|---|
| 1 | Public | `POST /companies/register` | identité, fiscalité, mandat PDF | honeypot, 3/IP/h, PDF valide (≤5 Mo, signature, non chiffré), recherche d'un doublon ou d'une demande `REJECTED`/`EMAIL_VERIFICATION_PENDING` réouvrable (`app/company/registration.py:258-351`) | `Company` statut `EMAIL_VERIFICATION_PENDING`, `User(ENTERPRISE, password_hash=None)` | e-mail avec code à 6 chiffres |
| 2 | Public | `POST /companies/registration/verify-email` | code | 30 min, 5 tentatives, 20/IP/h (`app/company/verification_email.py`) | statut `PENDING_ONBOARDING`, jeton de suivi émis | notification à tous les ADMIN actifs ; e-mail d'accusé avec lien de suivi |
| 3 | ADMIN | `GET /admin/companies/{id}/kyc` (optionnel) | — | 4 contrôles recalculés à la volée, jamais bloquants (`app/admin/kyc.py`) | rapport affiché | — |
| 4 | ADMIN | `PATCH /admin/companies/{id}/onboard` (APPROVE) | — | verrou de ligne, statut `PENDING_ONBOARDING`/`INFO_REQUESTED` requis (`app/admin/onboarding.py:117-216`) | `ACTIVE`, `onboarded_at/by_id` | lien d'activation 72h envoyé |
| 4′ | ADMIN | idem (REQUEST_INFO) | message | — | `INFO_REQUESTED`, nouveau jeton (ancien invalidé) | e-mail avec message + lien |
| 4″ | ADMIN | idem (REJECT) | motif requis | — | `REJECTED`, `User.active=False` | e-mail avec motif |
| 5 | Public (jeton, si INFO_REQUESTED) | `POST /companies/registration-status/reply` | nouveau mandat, message ≤2000 car. | 3/IP/h, row locked | retour à `PENDING_ONBOARDING` | ré-notification des ADMIN |
| 6 | Titulaire | `POST /auth/activer-compte` | mot de passe (≥12 car.) | jeton 72h, usage unique | mot de passe défini, **session ouverte immédiatement** | — |

Condition bloquante en aval : `verifier_entreprise_active` (`app/company/rapports.py:89-103`)
interdit tout dépôt de rapport tant que la société n'est pas `ACTIVE`.

### 7.2 Demande d'accès Investisseur / Chercheur

Structurellement identique à 7.1 (mêmes règles anti-fuite, mêmes limites de débit, réutilise les
mêmes fonctions utilitaires que `app/company/registration.py`), en plus court :
`POST /access-requests` (public) → `User(role, password_hash=None)` + `AccessRequest
PENDING_APPROVAL` → `PATCH /admin/access-requests/{id}` (ADMIN, APPROVE avec lien d'activation 72h,
ou REJECT avec motif obligatoire et désactivation du compte).

### 7.3 Cycle de vie du rapport ESG — vue d'ensemble

| # | Acteur | Action | Module/service | Entrée | Traitement | Validation/condition | Sortie | Job | Acteur suivant |
|---|---|---|---|---|---|---|---|---|---|
| 1 | ENTERPRISE/ADMIN | Ouvrir une session | `app/reporting/sessions.py:102-148` | exercice, type | règles d'exercice (une déclaration active, exercice non déjà validé) | société `ACTIVE` | `DRAFT` | — | ENTERPRISE |
| 2 | ENTERPRISE/ADMIN | Joindre un fichier | `sessions.py:189-202` → `rapports.py` | PDF | magic bytes, somme de contrôle, déduplication | `DRAFT` verrouillé | `EXTRACTING`, pas de `submitted_at` | `extract_report` (après commit, `rapports.py:208`) | Worker |
| 3 | Worker | Pipeline d'extraction | `app/ingestion/extractor.py` | PDF stocké | voir §7.4 | statut encore `EXTRACTING` (garde anti-rejoue) | `DRAFT` (si non soumis) ou `AWAITING_ASSIGNMENT` | synthèse PDF (synchrone si non-brouillon) | ENTERPRISE |
| 4 | ENTERPRISE/ADMIN | Soumettre | `sessions.py:205-251` | — | fichier présent, analyse réussie, société `ACTIVE` | `DRAFT` analysé | `submitted_at` figé, `AWAITING_ASSIGNMENT` | `generate_synthesis_pdf` | ADMIN |
| 5 | ADMIN | Affecter un auditeur | `app/audit/assignment.py:28-74` | `auditor_id` | cible = AUDITOR actif, pas déjà affecté | `AWAITING_ASSIGNMENT` | `IN_AUDIT` | — | AUDITOR |
| 6 | AUDITOR | Revoir chaque valeur | `app/audit/revue.py:43-85` | décision par valeur | revue close après l'avis | `IN_AUDIT` | ligne `MetricReview` + mirroir sur la valeur | — | AUDITOR |
| 7 | AUDITOR | Rendre un avis | `app/audit/opinion.py:31-97` | décision globale + commentaire si ≠FAVORABLE | toutes valeurs revues (422 sinon) | `IN_AUDIT` | `AuditOpinion`, `PENDING_DECISION` | — | ADMIN |
| 8 | ADMIN | **Valider** (voir détail §7.6) | `app/admin/review_queue.py:316-349` | commentaire optionnel | verrou + avis existant + score calculable + couverture suffisante | `PENDING_DECISION` | `VALIDATED` + `Score` + dénormalisation | `generate_synthesis_pdf` | INVESTOR/RESEARCHER (après publication) |
| 8′ | ADMIN | Rejeter / Demander correction | `review_queue.py:267-313` | commentaire | `PENDING_DECISION` | `REJECTED` / `REVISION_REQUESTED` | — | ENTERPRISE (si correction) |
| 9 | ENTERPRISE | Nouvelle version | — | nouveau fichier | depuis `REVISION_REQUESTED` | — | nouveau `ESGReport` (`version+1`, `previous_report_id`), `EXTRACTING` | `extract_report` | retour à l'étape 3 |

**Étapes automatiques** : 2→3 (extraction), relance programmée des extractions bloquées (cron,
toutes les 5 min). **Étapes manuelles** : toutes les décisions humaines (soumission, affectation,
revue, avis, décision admin). **Étapes conditionnelles** : retour en brouillon vs. mise en file
selon que le rapport était déjà soumis au moment de l'analyse ; blocage de la validation si
couverture insuffisante (mécanisme présent mais dormant, voir §16). **Étape bloquante** :
l'extraction (une seule à la fois par worker, `max_jobs=1` sur la file dédiée).

### 7.4 Pipeline d'extraction documentaire (détail de l'étape 3 ci-dessus)

Entièrement interne au Worker (`app/ingestion/extractor.py:638-1023`), sans action humaine :

1. Garde de concurrence : abandon silencieux si le rapport n'est plus `EXTRACTING`.
2. Ouverture d'une ligne `ExtractionRun` (`RUNNING`) avant tout traitement.
3. Préchauffage du modèle d'embedding (bge-m3) — ordre technique obligatoire avant Docling/PaddleOCR.
4. Conversion Docling du PDF (OCR PaddleOCR si nécessaire).
5. Indexation sémantique (chunks → bge-m3 → FAISS `IndexFlatIP`, en mémoire).
6. Recherche sémantique **par indicateur cible** (une requête dédiée par code), sélection adaptative
   des pages par budget de tokens.
7. Appel LLM (Gemini `gemini-3.6-flash`, repli `gemini-3.5-flash` si quota épuisé) avec appel de
   fonction forcé (schéma JSON typé) — **ou**, si la clé API est un placeholder, génération d'une
   extraction de démonstration déterministe (`demo-synthetique`), jamais utilisée en production.
8. Récupération de page manquante par relocalisation si le LLM omet la citation de page.
9. Génération de la preuve (une mini-PDF d'une page par page citée, une ligne `Evidence` par page,
   partagée par toutes les valeurs de cette page) + calcul des boîtes de surbrillance.
10. Persistance (remplacement complet des indicateurs/carbone/couverture précédents de ce rapport).
11. Calcul de la couverture par indicateur cible (`TROUVE`/`NON_TROUVE`/`ABSENT_CONFIRME`).
12. Transition finale : `DRAFT` (brouillon non soumis) ou `AWAITING_ASSIGNMENT` ; `ExtractionRun`
    → `SUCCEEDED`.
    - **En cas d'échec transitoire** (5xx, 429 non-quota, réseau) : retour en file avec délai
      croissant, jusqu'à 3 tentatives.
    - **En cas d'échec définitif** : `EXTRACTION_FAILED` (ou retour `DRAFT`), cause classifiée
      fixe (jamais le message brut de l'exception).

### 7.5 Décision et publication atomique du score (détail de l'étape 8)

1. Verrouillage du rapport (`SELECT … FOR UPDATE`), re-vérification du statut `PENDING_DECISION`.
2. **Le statut est mis à `VALIDATED` avant le calcul du score** (ordre réel du code — voir §17 pour
   l'écart avec la documentation cible, sans impact sur l'atomicité car rien n'est commité avant la
   fin).
3. Résolution de la configuration de référence par **empreinte SHA-256 du contenu canonique** —
   `INSERT … ON CONFLICT DO NOTHING`, jamais de commit intermédiaire.
4. Calcul du score : valeur effective par indicateur (valeur auditée si `OVERRIDDEN`, exclue si
   `NOT_FOUND`, sinon valeur extraite) ; moyenne pondérée par pilier puis globale, renormalisée sur
   les seuls indicateurs/piliers présents.
5. Si un seuil de couverture minimal est défini dans la configuration et non atteint : exception,
   **rien n'est commité**, le rapport reste `PENDING_DECISION`.
6. Insertion de la ligne `Score`, dénormalisation de `official_score`/`coverage_rate`/`config_hash`
   sur le rapport.
7. Notification à l'entreprise.
8. `COMMIT` unique.
9. Après commit (best-effort) : enfilage de `generate_synthesis_pdf`.

### 7.6 Portefeuille investisseur — création, import, consultation

1. INVESTOR crée un portefeuille (`POST /investor/portefeuilles`) — devise USD fixée.
2. Import (une fois, portefeuille vide) : fichier CSV/JSON → validation ligne par ligne →
   rapprochement contre les entreprises **publiées** par ISIN/ticker → conversion de devise au taux
   figé à l'import → écriture tout-ou-rien.
3. Lecture (à chaque `GET`, **sans job ni cache** — voir §17) : agrégation pondérée du score ESG,
   couverture, puis empreinte carbone PCAF (facteur d'attribution, émissions financées par scope,
   WACI, qualité de donnée), chaque ligne exclue étant motivée (`UNMATCHED`,
   `NO_VALIDATED_REPORT`, `MISSING_EMISSIONS`, `MISSING_EVIC`).

### 7.7 Gouvernance de recherche — de l'invitation à l'analyse décidée

1. INSTITUTION invite un RESEARCHER → `ResearcherAffiliation` `EN_ATTENTE`.
2. RESEARCHER accepte → `ACCEPTE`.
3. INSTITUTION crée un `Project` (`OUVERT`), y affecte le chercheur accepté, y ajoute des
   entreprises publiées (périmètre) et leurs rapports **actuellement publiés** (documents).
4. RESEARCHER (affecté au projet, projet `OUVERT`) crée une `Analysis` `BROUILLON` sur ≥1
   entreprise du périmètre du projet (chacune publiée, avec score officiel résolvable — snapshot
   `report_id`/`score_id` figé définitivement à cet instant).
5. RESEARCHER soumet → `SOUMISE`.
6. INSTITUTION décide : `VALIDEE` ou `CORRECTION_DEMANDEE` (commentaire obligatoire dans ce cas).
7. Si correction demandée : RESEARCHER crée une nouvelle version (`version+1`,
   `previous_analysis_id`) → retour à l'étape 5.
8. INSTITUTION peut exporter une analyse décidée en CSV, dans la limite de son quota.

### 7.8 Validation croisée (chercheur)

1. RESEARCHER importe un CSV externe (≤5 Mo/20 000 lignes) avec licence/source déclarées et un
   couple (`scale_min`,`scale_max`,`higher_is_better`) — import **partiel** (lignes invalides
   ignorées, échec total seulement si zéro ligne importée).
2. Rapprochement par ISIN puis LEI, limité au périmètre cumulé des projets du chercheur, parmi les
   entreprises publiées avec score officiel.
3. Calcul : corrélation de rang de Spearman (si ≥3 paires) + écart absolu moyen par pilier (valeurs
   du jeu externe ramenées sur 0–100) — jamais d'écriture sur les données de la plateforme.

---

## 8. Données pour le diagramme de classes

### 8.1 Convention de lecture

Pour chaque entité : **Identité** (module, rôle), **Attributs** (type, obligatoire, défaut, PK/FK,
enum, contrainte), **Méthodes métier** (une seule entité en a, voir 8.3.7), puis une table unique de
**Relations** (8.5) couvrant tout le schéma. Toutes les énumérations sont listées en 8.4. Les
classes sans `models.py` propre (`admin`, `explainability`, `carbon`, `reporting`) réutilisent les
entités ci-dessous — elles n'ajoutent aucune classe persistée.

### 8.2 `app/core/models.py`

**`AuditLogEntry`** (table `audit_log`) — journal d'événements de compte/session, jamais des
entreprises (règle explicite, voir §16-RG14).
| Attribut | Type | Oblig. | Déf. | Clé/contrainte |
|---|---|---|---|---|
| id | UUID | oui | uuid4 | PK |
| actor_id | UUID | non | — | FK→users, SET NULL |
| action | str | oui | — | code anglais (ex. `login`) |
| resource_type | str | oui | — | code anglais (ex. `User`) |
| resource_id | UUID | non | — | |
| occurred_at | datetime | oui | utcnow | |
| result | str | oui | — | ex. `success` |
| old_value, new_value, correlation_id, ip | str | non | — | `ip` jamais alimenté actuellement |

**`Notification`** (table `notifications`)
| Attribut | Type | Oblig. | Déf. | Clé/contrainte |
|---|---|---|---|---|
| id | UUID | oui | uuid4 | PK |
| user_id | UUID | oui | — | FK→users, CASCADE |
| message | str | oui | — | |
| type | str | oui | — | chaîne libre, pas un enum colonne |
| resource_id | UUID | non | — | jamais une FK stricte (cible variable selon `type`) |
| sent_at | datetime | oui | utcnow | |
| read | bool | oui | False | |

### 8.3 `app/auth/models.py`

**`User`** (table `users`) — compte, racine de toutes les relations de rôle.
| Attribut | Type | Oblig. | Déf. | Clé/contrainte |
|---|---|---|---|---|
| id | UUID | oui | uuid4 | PK |
| email | str | oui | — | unique, indexé, CHECK `email=lower(email)` |
| name | str | non | — | |
| avatar_path | str | non | — | chemin relatif sous STORAGE_PATH |
| password_hash | str | non | — | `None` jusqu'à activation |
| role | Role (enum) | oui | — | |
| created_at | datetime | oui | utcnow | |
| active | bool | oui | True | |
| activated_at | datetime | non | — | |

**`PasswordResetToken`** / **`AccountActivationToken`** / **`EmailChangeRequest`** — même forme :
id, `user_id` (FK→users CASCADE, indexé), `token_hash` (SHA-256, unique, indexé — jamais le jeton
brut), `created_at`, `expires_at`, `used_at` (marqueur d'usage unique) ; `EmailChangeRequest` ajoute
`new_email`.

**`InstitutionProfile`** (table `institution_profiles`) : id, `user_id` (FK→users CASCADE,
**unique** — extension 1-1), `export_quota` (int).

**`ResearcherAffiliation`** (table `researcher_affiliations`) : id, `researcher_id` (FK→users
CASCADE), `institution_id` (FK→users CASCADE, indexé), `status` (AffiliationStatus, déf.
`EN_ATTENTE`), `invited_at`, `responded_at`, `collaboration_terms`. Contrainte unique
`(researcher_id, institution_id)`. Aucune `relationship()` SQLAlchemy déclarée (deux FK vers la
même table `users` nécessiteraient `foreign_keys=` explicite).

### 8.4bis `app/company/models.py`

**`Company`** (table `companies`) — fiche maîtresse.
| Attribut | Type | Oblig. | Déf. | Notes |
|---|---|---|---|---|
| id | UUID | oui | uuid4 | PK |
| name, sector, country | str | oui | — | `country` en texte libre (pas encore ISO-2 forcé) |
| logo | str | non | — | encore une donnée-URI, pas un chemin fichier |
| description, website | str | non | — | |
| status | RegistrationStatus | oui | `ACTIVE` (valeur par défaut colonne) | voir §15 pour le cycle réel |
| owner_user_id | UUID | non | — | FK→users, SET NULL |
| email_verification_code_hash/_sent_at/_expires_at/_attempts/_verified_at | — | non/oui(attempts=0) | — | tâche 5.11 |
| tax_id, tax_id_type | str/TaxIdType | non | — | |
| isin, lei | str | non | — | **uniques chacun** |
| ticker | str | non | — | indexé, **jamais unique** (plusieurs places de cotation) |
| minimum_investment_amount/_currency | Decimal(20,2)/Currency | non | — | toujours ensemble |
| published_at | datetime | non | — | fait aussi office de booléen « publiée » |
| onboarded_at/_by_id, registered_at, status_token_hash, mandate_letter_path/_uploaded_at, info_request_message/_requested_at/_response_message, rejection_reason/_rejected_at | — | non | — | cycle d'inscription, voir §15 |

Aucune méthode métier sur la classe.

### 8.4ter `app/access_requests/models.py`

**`AccessRequest`** : id, `user_id` (FK→users CASCADE, **unique**), `role` (Role, CHECK ∈
{INVESTOR,RESEARCHER}), `organization`, `investor_type`/`research_domain` (exactement un des deux,
CHECK croisé avec `role`), `status` (AccessRequestStatus, déf. `PENDING_APPROVAL`),
`requested_at`, `decided_at`, `decided_by_id` (FK→users SET NULL), `rejection_reason`.

### 8.5 `app/audit/models.py`

**`AuditOpinion`** : id, `report_id` (FK→esg_reports CASCADE), `auditor_id` (FK→users
**RESTRICT**), `decision` (AuditDecision), `comment`, `submitted_at`.

**`MetricReview`** — append-only (déclencheur PostgreSQL, voir §16-RG08) : id, `report_id`
(FK→esg_reports RESTRICT), `metric_id`/`emission_id` (exactement un des deux, FK RESTRICT chacun),
`decision` (MetricReviewStatus, ≠`PENDING`), `original_value`, `new_value` (ssi `OVERRIDDEN`),
`reason` (requis sauf `ACCEPTED`), `comment`, `auditor_id` (FK RESTRICT), `created_at`.

### 8.6 `app/ingestion/models.py`

**`ESGReport`** (table `esg_reports`) — cœur du domaine.
| Attribut | Type | Oblig. | Notes |
|---|---|---|---|
| id | UUID | oui | PK |
| company_id | UUID | oui | FK→companies, CASCADE |
| type, channel | ReportType, SubmissionChannel | oui | |
| created_at, submitted_at | datetime | — | `submitted_at` NULL = verrou non posé |
| status | ReportStatus | oui, déf. `EXTRACTING` | voir §15 |
| source_file, original_filename | str | non | NULL seulement en `DRAFT` |
| fiscal_year | int | non | indexé avec `company_id` (non unique : plusieurs types/corrections par exercice) |
| auditor_id, assigned_at | UUID/datetime | non | FK→users SET NULL |
| extraction_started_at/_finished_at/_error/_attempts | — | — | pilotage du pipeline |
| version, previous_report_id | int/UUID | oui/non | FK self SET NULL, chaîne de correction |
| checksum_sha256 | str | non | indexé |
| declared_global_score, declared_global_score_proof_id | float/UUID | non | FK→evidence SET NULL |
| synthesis_report_path | str | non | |
| official_score, coverage_rate | float | non | **flottants simples, sans CHECK de plage en base** (écart doc, §17) |
| config_hash | str | non | |
| revenue/_currency, enterprise_value/_currency, evic_date | Decimal/Currency/date | non | PCAF, par exercice |

Contraintes : unique `(company_id, checksum_sha256)` ; index `(company_id, fiscal_year)` ; unique
partiel `(company_id, fiscal_year, type)` **où** `submitted_at IS NULL` (un seul brouillon/non-soumis
à la fois) ; CHECK liant statut à présence de fichier/`submitted_at`.

**`ExtractionRun`** : id, `report_id` (FK CASCADE), `started_at`, `finished_at`, `status`
(ExtractionRunStatus, déf. `RUNNING`), `error`, `docling_version`, `llm_model`, `prompt_version`.

**`Evidence`** : id, `document_name`, `year`, `total_pages`, `page_start`, `page_end`,
`excerpt_pdf_path`. Une ligne peut être partagée par plusieurs `ESGMetric`/`CarbonEmission` (toutes
les valeurs d'une même page de preuve).

**`ESGMetric`** : id, `report_id` (FK CASCADE), `pillar` (Pillar), `metric_code`, `value`, `unit`,
`method` (DataMethod), `proof_id` (FK→evidence CASCADE), `raw_value`, `section`, `proof_text`,
`value_year`, `confidence` (ConfidenceLevel), `extraction_run_id` (FK SET NULL), `proof_boxes`
(JSONB, déf. `[]`), `review_status` (MetricReviewStatus, déf. `PENDING`), `audited_value`.
Contrainte unique `(report_id, metric_code)`.

**`CarbonEmission`** : id, `report_id` (FK CASCADE), `scope` (1/2/3, CHECK), `ghg_category`
(`market_based`/`location_based`), `tonnes_co2e` (CHECK ≥0), `year`, `method` (DataMethod),
`pcaf_data_quality` (1–5, CHECK, **nullable** — jamais de valeur fabriquée), `proof_id` (FK CASCADE),
+ mêmes champs de traçabilité et de revue que `ESGMetric`.

**`MetricCoverage`** : id, `report_id` (FK CASCADE), `metric_code`, `status`
(MetricCoverageStatus), `pages_examined`. Unique `(report_id, metric_code)` ; remplacée en bloc à
chaque tentative d'extraction (non versionnée).

**`DiscrepancyFlag`** : id, `metric_id` (FK CASCADE), `company_id` (FK CASCADE), `nature`,
`status` (chaîne libre, défaut `"OUVERT"`, **pas d'enum** — à noter, §17), `flagged_at`.

### 8.7 `app/investor/models.py`

**`Portfolio`** : id, `user_id` (FK CASCADE), `name`, `reference_currency` (Currency), `created_at`,
`archived` (bool, déf. False), + colonnes d'agrégats en cache (`total_esg_score`, `waci`,
`financed_emissions_tco2e`, `computed_at`, `config_hash`) — **déclarées mais jamais écrites par
aucun code** (voir §17 ; tout est recalculé à la lecture).

**`PortfolioPosition`** : id, `portfolio_id` (FK CASCADE), `company_id` (FK **CASCADE**, nullable —
ligne d'import non rapprochée), `identifier_type`/`identifier_raw`, `match_status` (MatchStatus,
déf. `MATCHED`), `outstanding_amount` (Decimal(20,2), CHECK >0), `currency`, `fx_rate_used`
(Decimal(20,10), nullable), `converted_amount` (Decimal(20,2), toujours renseigné), `weight`
(Decimal(11,10), CHECK ∈(0,1] si non nul), `duration_type` (DurationType), `start_date`, `end_date`.
CHECK croisé : `match_status='MATCHED' ⇔ company_id IS NOT NULL`.

**Méthodes métier** (seule entité du schéma à en avoir — validateurs Pydantic `mode="after"`,
déclenchés à la construction et à toute affectation car `validate_assignment=True`) :
- `_valider_regles_duree()` — règles de durée : `FIXE` exige `end_date`, `start_date ≥ aujourd'hui`,
  `end_date ≤ start_date+365j`, `end_date > start_date` ; `OUVERTE` exige `start_date ≥ aujourd'hui`
  seulement si `end_date` encore absente.
- `_valider_montant_minimum(info)` — si un contexte Pydantic `{"entreprise": ...}` est fourni,
  rejette un montant inférieur au minimum d'investissement déclaré par l'entreprise (en pratique,
  l'application préfère une fonction de service séparée pour cette vérification — voir §17, ce
  validateur est un filet de sécurité qui n'est pas toujours exercé).

### 8.8 `app/institution/models.py`

**`Project`** : id, `institution_id` (FK→users **RESTRICT**), `name`, `description`, `objective`
(deux champs texte distincts), `start_date`, `planned_end_date`, `deadline`, `status`
(ProjectStatus, déf. `OUVERT`), `created_at`, `closed_at`.

**`ProjectAssignment`** : id, `project_id` (FK CASCADE), `researcher_id` (FK→users **RESTRICT**),
`assigned_at`. Unique `(project_id, researcher_id)`.

**`ProjectCompany`** : id, `project_id` (FK CASCADE), `company_id` (FK CASCADE), `added_at`. Unique
`(project_id, company_id)`.

**`ProjectDocument`** : id, `project_id` (FK CASCADE), `report_id` (FK→esg_reports CASCADE),
`added_at`. Unique `(project_id, report_id)`.

### 8.9 `app/researcher/models.py`

**`Analysis`** : id, `project_id` (FK **RESTRICT** — « un travail livré ne disparaît jamais avec son
projet »), `researcher_id` (FK **RESTRICT**), `title`, `content`, `status` (AnalysisStatus, déf.
`BROUILLON`), `version` (déf. 1), `previous_analysis_id` (FK self SET NULL), `institution_comment`,
`created_at`, `submitted_at`, `decided_at`.

**`AnalysisCompany`** : id, `analysis_id` (FK CASCADE), `company_id` (FK CASCADE), `report_id`
(FK SET NULL, **figé au moment de l'ajout**), `score_id` (FK SET NULL, **figé**). Unique
`(analysis_id, company_id)`.

**`ReferenceDataset`** : id, `owner_user_id` (FK CASCADE), `name`, `source_url`, `licence`,
`scale_min`, `scale_max` (CHECK `scale_max>scale_min`), `higher_is_better`, `created_at`. Cascade
ORM `all, delete-orphan` vers ses lignes.

**`ReferenceDatasetRow`** : id, `dataset_id` (FK CASCADE), `line_number`, `isin`, `lei`,
`company_name`, `environmental_score`, `social_score`, `governance_score`, `total_score`. CHECK
`isin IS NOT NULL OR lei IS NOT NULL`.

### 8.10 `app/scoring/models.py`

**`ScoringConfig`** : id, `name`, `version` (informatif — l'identité réelle est `content_hash`),
`content_yaml` (Text, nullable), `content_hash` (char(64), nullable), `created_at`,
`owner_user_id` (FK→users **RESTRICT**, nullable = configuration de référence). CHECK :
`content_yaml` et `content_hash` nuls ou non-nuls ensemble. Deux index uniques partiels (un pour
owner NULL, un par owner non-NULL) sur `content_hash`.

**`Score`** : id, `report_id` (FK CASCADE), `config_id` (FK **RESTRICT**), `global_score` (CHECK
0–100), `environmental_score`/`social_score`/`governance_score` (CHECK 0–100, nullable si pilier
absent), `coverage_rate` (CHECK 0–1), `computed_at`. Unique `(report_id, config_id)`.

### 8.11 Table des relations (vue consolidée)

| Source | Cible | Colonne FK | Nullable | ON DELETE | Nature UML | Justification |
|---|---|---|---|---|---|---|
| Notification | User | user_id | non | CASCADE | Composition | notification sans sens hors de son utilisateur |
| PasswordResetToken/AccountActivationToken/EmailChangeRequest | User | user_id | non | CASCADE | Composition | jetons entièrement possédés par le compte |
| InstitutionProfile | User | user_id | non, unique | CASCADE | Composition | extension 1-1 |
| ResearcherAffiliation | User (×2 rôles) | researcher_id / institution_id | non | CASCADE | Association (table de liaison) | lien entre deux comptes, pas une possession |
| Company | User (owner) | owner_user_id | oui | SET NULL | Association | une société peut exister sans compte attaché |
| ESGReport | Company | company_id | non | CASCADE | Composition | un rapport n'existe pas sans sa société |
| ESGReport | User (auditor) | auditor_id | oui | SET NULL | Association | affectation, pas possession |
| ESGReport | ESGReport (previous) | previous_report_id | oui | SET NULL | Dépendance (chaîne temporelle) | pointeur de version, jamais de ré-écriture |
| ExtractionRun | ESGReport | report_id | non | CASCADE | Composition | disparaît avec son rapport |
| ESGMetric / CarbonEmission | ESGReport | report_id | non | CASCADE | Composition | décomposition du rapport |
| ESGMetric / CarbonEmission | Evidence | proof_id | non | CASCADE | Composition (depuis la valeur) / partagée (depuis la preuve) | garantie « pas de valeur sans preuve » |
| ESGMetric / CarbonEmission | ExtractionRun | extraction_run_id | oui | SET NULL | Association | simple provenance |
| MetricCoverage | ESGReport | report_id | non | CASCADE | Composition | remplacée en bloc avec le rapport |
| DiscrepancyFlag | ESGMetric | metric_id | non | CASCADE | Composition | signalement lié à une valeur précise |
| DiscrepancyFlag | Company | company_id | non | CASCADE | Association (dénormalisation) | pointeur de confort pour requêtage |
| AuditOpinion | ESGReport | report_id | non | CASCADE | Composition | scopé entièrement au rapport |
| AuditOpinion / MetricReview | User (auditeur) | auditor_id | non | **RESTRICT** | Association protégée | la responsabilité ne doit jamais disparaître |
| MetricReview | ESGReport / ESGMetric / CarbonEmission | report_id / metric_id / emission_id | non / un des deux | **RESTRICT** | Association protégée (journal append-only) | trace inaltérable |
| Portfolio | User | user_id | non | CASCADE | Composition | portefeuille propriété exclusive de l'investisseur |
| PortfolioPosition | Portfolio | portfolio_id | non | CASCADE | Composition | position sans portefeuille impossible |
| PortfolioPosition | Company | company_id | oui | **CASCADE** | **Agrégation (ambigu, voir §17)** | nullable pour ligne non rapprochée, mais CASCADE plutôt que SET NULL sur le cas rapproché — intention non documentée |
| Project | User (institution) | institution_id | non | **RESTRICT** | Association protégée | compte non supprimable tant que des projets existent |
| ProjectAssignment / ProjectCompany / ProjectDocument | Project | project_id | non | CASCADE | Composition | enfants supprimés avec le projet |
| ProjectAssignment | User (researcher) | researcher_id | non | **RESTRICT** | Association protégée | |
| ProjectCompany | Company | company_id | non | CASCADE | Agrégation | la société vit indépendamment du périmètre qui la cite |
| ProjectDocument | ESGReport | report_id | non | CASCADE | Agrégation | le rapport vit indépendamment du projet qui le cite |
| Analysis | Project | project_id | non | **RESTRICT** | Association protégée | « travail livré », jamais supprimé avec le projet |
| Analysis | User (researcher) | researcher_id | non | **RESTRICT** | Association protégée | |
| Analysis | Analysis (previous) | previous_analysis_id | oui | SET NULL | Dépendance (chaîne de version) | |
| AnalysisCompany | Analysis | analysis_id | non | CASCADE | Composition | ligne de liaison possédée par l'analyse |
| AnalysisCompany | Company | company_id | non | CASCADE | Agrégation | |
| AnalysisCompany | ESGReport / Score | report_id / score_id | oui | SET NULL | Dépendance (instantané figé) | jamais mis à jour après coup, par conception |
| ReferenceDataset | User (owner) | owner_user_id | non | CASCADE | Composition | privé au chercheur auteur |
| ReferenceDatasetRow | ReferenceDataset | dataset_id | non | CASCADE (+ cascade ORM) | Composition | doublement garantie |
| ScoringConfig | User (owner) | owner_user_id | oui | **RESTRICT** | Association protégée | évite qu'une suppression de compte produise accidentellement une config « de référence » |
| Score | ESGReport | report_id | non | CASCADE | Composition | dérivée et possédée par le rapport |
| Score | ScoringConfig | config_id | non | **RESTRICT** | Association protégée | une méthodologie qui a produit des scores ne disparaît pas sous eux |

**Points signalés comme ambigus (ne pas trancher sans confirmation) :**
- `PortfolioPosition.company_id` : nullable + `ON DELETE CASCADE`. Combinaison inhabituelle (on
  attendrait `SET NULL` pour préserver la position comme « non rapprochée » en cas de suppression
  de l'entreprise). Le code ne documente que la nullabilité, pas ce choix de cascade.
- `Evidence` partagée par plusieurs valeurs avec cascade **depuis** les valeurs : la suppression
  d'une preuve supprime toutes les valeurs qui la citent. Le volume réel de partage (une page citée
  par une seule valeur vs. plusieurs) n'a pas été mesuré dans le code, seulement rendu possible par
  le modèle.

### 8.12 Enums (`app/core/enums.py`, stockage VARCHAR+CHECK, jamais de type ENUM natif PostgreSQL)

| Enum | Valeurs | Colonne(s) |
|---|---|---|
| `ReportStatus` | DRAFT, EXTRACTING, EXTRACTION_FAILED, AWAITING_ASSIGNMENT, IN_AUDIT, PENDING_DECISION, REVISION_REQUESTED, VALIDATED, REJECTED | `ESGReport.status` |
| `ExtractionRunStatus` | RUNNING, SUCCEEDED, FAILED, RETRY_SCHEDULED | `ExtractionRun.status` |
| `RegistrationStatus` | EMAIL_VERIFICATION_PENDING, PENDING_ONBOARDING, INFO_REQUESTED, ACTIVE, REJECTED, SUSPENDED | `Company.status` |
| `KycCheckResult` | PASSED, FAILED, NOT_VERIFIABLE, NOT_APPLICABLE | non lié à une colonne persistée (usage probable : schémas KYC uniquement — **non confirmé**) |
| `TaxIdType` | NIF, SIREN, EIN, TAX_ID | `Company.tax_id_type` |
| `AccessRequestStatus` | PENDING_APPROVAL, APPROVED, REJECTED | `AccessRequest.status` |
| `InvestorType` | INVESTMENT_FUND, BANK_INSTITUTIONAL, BUSINESS_ANGEL, OTHER | `AccessRequest.investor_type` |
| `ResearchDomain` | SUSTAINABLE_FINANCE, CARBON_FOOTPRINT, GOVERNANCE, OTHER | `AccessRequest.research_domain` |
| `ReportType` | RAPPORT_ANNUEL, RAPPORT_ESG, RAPPORT_CLIMAT | `ESGReport.type` |
| `SubmissionChannel` | AUTOMATIQUE, ENTREPRISE | `ESGReport.channel` |
| `Pillar` | ENVIRONNEMENT, SOCIAL, GOUVERNANCE | `ESGMetric.pillar` |
| `DataMethod` | RAPPORTEE, ESTIMEE, CALCULEE | `ESGMetric.method`, `CarbonEmission.method` |
| `MetricCoverageStatus` | TROUVE, NON_TROUVE, ABSENT_CONFIRME | `MetricCoverage.status` |
| `ConfidenceLevel` | ELEVE, MOYEN, FAIBLE | `ESGMetric.confidence`, `CarbonEmission.confidence` |
| `AuditDecision` | FAVORABLE, FAVORABLE_WITH_RESERVATIONS, CORRECTION_REQUIRED, UNFAVORABLE | `AuditOpinion.decision` |
| `MetricReviewStatus` | PENDING, ACCEPTED, OVERRIDDEN, NOT_FOUND | `MetricReview.decision`, `ESGMetric/CarbonEmission.review_status` |
| `ReviewReason` | EXTRACTION_ERROR, UNIT_ERROR, WRONG_PERIOD, WRONG_SCOPE, NOT_IN_SOURCE, OTHER | `MetricReview.reason` |
| `Role` | ADMIN, ENTERPRISE, AUDITOR, INVESTOR, RESEARCHER, INSTITUTION | `User.role`, `AccessRequest.role` |
| `Currency` | MRU, USD, EUR | plusieurs colonnes monétaires |
| `BaselineScope` | SECTOR, UNIVERSE | non lié à une colonne persistée — paramètre de requête/schéma uniquement |
| `ComparedScore` | ENVIRONMENTAL, SOCIAL, GOVERNANCE, GLOBAL | non lié à une colonne persistée — logique de validation croisée |
| `UnmatchedReason` | UNKNOWN, DUPLICATE, NO_PLATFORM_SCORE | calculé à la lecture, jamais stocké |
| `IdentifierType` | ISIN, TICKER | `PortfolioPosition.identifier_type` |
| `MatchStatus` | MATCHED, UNMATCHED, AMBIGUOUS | `PortfolioPosition.match_status` |
| `DurationType` | OUVERTE, FIXE | `PortfolioPosition.duration_type` |
| `AffiliationStatus` | EN_ATTENTE, ACCEPTE, REFUSE | `ResearcherAffiliation.status` |
| `ProjectStatus` | OUVERT, CLOTURE | `Project.status` |
| `AnalysisStatus` | BROUILLON, SOUMISE, VALIDEE, CORRECTION_DEMANDEE | `Analysis.status` |

Énumérations locales (non persistées, utilisées seulement en entrée/sortie d'API) :
`OnboardingDecision`, `RequestedRole`, `AccessDecision`, `CarbonExclusionReason` (calculée),
`EtatPosition` (calculée, présentation uniquement — `PLANIFIEE/ACTIVE/CLOTUREE/
ENTREPRISE_SUSPENDUE`).

---

## 9. Données pour les diagrammes de cas d'utilisation

### 9.A Cas d'utilisation général (acteurs → grandes fonctionnalités)

| Acteur | Grandes fonctionnalités |
|---|---|
| Public | S'inscrire (entreprise) ; Vérifier son e-mail ; Suivre une demande ; Demander un accès (investisseur/chercheur) ; Contacter la plateforme |
| ADMIN | Décider des inscriptions (KYC) ; Gérer les comptes ; Affecter un auditeur ; Décider d'un rapport ; Publier/suspendre une entreprise ; Saisir les données financières PCAF ; Consulter le journal d'audit ; Superviser (portefeuilles/analyses/projets en lecture) |
| ENTERPRISE | Déposer/corriger un rapport ; Suivre son statut ; Télécharger la synthèse ; Gérer son profil |
| AUDITOR | Examiner un dossier affecté ; Revoir chaque valeur ; Rendre un avis |
| INVESTOR | Consulter/comparer les entreprises publiées ; Gérer des portefeuilles ; Importer des positions ; Consulter l'empreinte carbone |
| RESEARCHER | Répondre à une invitation ; Rédiger/soumettre/corriger une analyse ; Importer un jeu de données de référence ; Lancer une validation croisée |
| INSTITUTION | Inviter un chercheur ; Créer/clôturer un projet ; Définir un périmètre ; Décider d'une analyse ; Exporter |

### 9.B Cas d'utilisation détaillés (par domaine)

**Domaine inscription entreprise (Public, ADMIN)**
- *Cas principal* : « S'inscrire en tant qu'entreprise ». Sous-cas : vérifier l'e-mail, suivre la
  demande, répondre à une demande d'information. Précondition : aucune. Résultat : société
  `ACTIVE` ou `REJECTED`.
- *Cas* : « Décider d'une inscription » (ADMIN). **include** « Consulter le rapport KYC » (toujours
  consulté dans le même écran avant décision — mais n'empêche jamais la décision : include car
  systématiquement affiché, pas une condition). Sous-cas : approuver, rejeter, demander une info.

**Domaine rapport ESG (ENTERPRISE, ADMIN, AUDITOR)**
- *Cas principal* : « Déposer un rapport ESG » (ENTERPRISE). **include** « Joindre un fichier »
  (étape obligatoire du dépôt). **extend** « Importer par URL » (variante du dépôt, optionnelle).
  Précondition : société `ACTIVE`. Résultat : rapport `AWAITING_ASSIGNMENT`.
- *Cas* : « Examiner un dossier » (AUDITOR). **include** « Revoir une valeur » (répété pour chaque
  valeur — l'avis ne peut être rendu sans que toutes les revues existent, lien de dépendance fort).
  **include** « Rendre un avis d'audit ». Précondition : dossier affecté, statut `IN_AUDIT`.
- *Cas* : « Décider d'un rapport » (ADMIN). **include** « Calculer le score » (seulement pour la
  branche « Valider » — la validation déclenche toujours le calcul dans la même transaction).
  **extend** « Recalculer un score manquant » (cas de réparation, hors chemin normal).
  Précondition : statut `PENDING_DECISION`, avis d'audit existant.

**Domaine investisseur (INVESTOR)**
- *Cas principal* : « Consulter le catalogue des entreprises publiées ». **extend** « Comparer
  jusqu'à 4 entreprises » (extension optionnelle du catalogue).
- *Cas* : « Gérer un portefeuille ». **include** « Ajouter une position » / « Importer des
  positions » (deux manières alternatives d'alimenter un portefeuille — plutôt deux cas distincts
  reliés par généralisation que par include, car ni l'un ni l'autre n'est une sous-étape
  obligatoire du premier). **extend** « Consulter l'empreinte carbone » (toujours disponible une
  fois des positions rapprochées présentes, mais optionnelle).

**Domaine recherche (INSTITUTION, RESEARCHER)**
- *Cas principal* : « Encadrer un projet de recherche » (INSTITUTION). **include** « Inviter un
  chercheur », « Définir le périmètre », « Affecter un chercheur au projet » (toutes obligatoires
  pour qu'une analyse devienne possible). **extend** « Attacher un document ».
- *Cas* : « Décider d'une analyse » (INSTITUTION). Précondition stricte : statut `SOUMISE`
  (jamais `BROUILLON`, invisible à l'institution par conception).
- *Cas principal* : « Rédiger une analyse » (RESEARCHER). **include** « Soumettre l'analyse ».
  **extend** « Corriger après une demande » (seulement si l'institution l'a demandé).
- *Cas* : « Lancer une validation croisée » (RESEARCHER). **include** « Importer un jeu de données
  de référence » (précondition obligatoire : le jeu doit exister avant tout rapport de corrélation).

**Dépendances transverses** : tout cas d'utilisation d'un rôle authentifié dépend (relation de
dépendance technique, pas UML « include » fonctionnel) du cas générique « Se connecter » — non
répété dans chaque domaine pour éviter le bruit, mais à représenter une fois dans le diagramme
général.

---

## 10. Données pour 3 diagrammes de séquence

### Scénario 1 — Dépôt et extraction automatique d'un rapport ESG

**Objectif** : montrer la bascule synchrone→asynchrone et le pipeline IA.
**Acteur déclencheur** : ENTERPRISE.
**Participants techniques** : Navigateur (React) ; API `/api/v1` (routeur `reporting`) ; service
`app/reporting/sessions.py`/`app/company/rapports.py` ; file ARQ `arq:extraction` ; Worker
d'extraction ; Docling/PaddleOCR ; bge-m3+FAISS ; Gemini (ou mode démo) ; PostgreSQL ; stockage
fichiers.

| # | Émetteur | Destinataire | Action | Données | Résultat | Condition |
|---|---|---|---|---|---|---|
| 1 | ENTERPRISE | Navigateur | Sélectionne un PDF, soumet | fichier | — | brouillon `DRAFT` existant |
| 2 | Navigateur | API | `POST /reports/{id}/file` (multipart) | fichier | — | — |
| 3 | API | Service `sessions.py` | `joindre_fichier` | fichier | validation magic bytes + somme de contrôle | PDF invalide → 422 |
| 4 | Service | PostgreSQL | `UPDATE esg_reports SET status='EXTRACTING', source_file=…` | — | commit | brouillon verrouillé (`FOR UPDATE`) |
| 5 | Service | File ARQ `arq:extraction` | Enfile `extract_report` (après commit) | `report_id` | job id déterministe `extract:{id}` | dédoublonnage automatique si déjà en file |
| 6 | API | Navigateur | 200, rapport `EXTRACTING` | — | — | — |
| 7 | Navigateur | API | `GET /reports/{id}` (sondage toutes les 5s) | — | statut courant | tant que `EXTRACTING` |
| 8 | Worker | PostgreSQL | Ouvre une session propre, vérifie `status==EXTRACTING` (garde anti-rejoue) | — | — | sinon abandon silencieux |
| 9 | Worker | PostgreSQL | Insère `ExtractionRun(RUNNING)` | modèle/version Docling, LLM, prompt | — | — |
| 10 | Worker | Docling+PaddleOCR | Convertit le PDF | fichier | document structuré | — |
| 11 | Worker | bge-m3 | Encode les chunks + requêtes par indicateur | texte | vecteurs | — |
| 12 | Worker | FAISS | Recherche sémantique par code cible | vecteurs | pages pertinentes classées | — |
| 13 | Worker | Gemini (`gemini-3.6-flash`) | Appel de fonction forcé avec les pages sélectionnées | schéma JSON typé | valeurs + citations + page source | **si clé API = placeholder** : génère des valeurs de démonstration déterministes à la place (aucun appel réseau) |
| 14 | Worker | PyMuPDF | Découpe une mini-PDF par page citée | page source | `Evidence` + boîtes de surbrillance | — |
| 15 | Worker | PostgreSQL | Remplace `ESGMetric`/`CarbonEmission`/`MetricCoverage` du rapport, calcule la couverture | valeurs extraites | — | — |
| 16 | Worker | PostgreSQL | `status` → `DRAFT` (si non soumis) ou `AWAITING_ASSIGNMENT` ; `ExtractionRun` → `SUCCEEDED` | — | commit | en cas d'échec transitoire : remise en file avec délai croissant (≤3 tentatives) ; sinon `EXTRACTION_FAILED` |
| 17 | Worker | Génération synthèse | Génère la synthèse PDF en tâche synchrone (si rapport non-brouillon) | — | fichier stocké | best-effort, jamais bloquant |
| 18 | Navigateur | API | Prochain sondage voit le nouveau statut, arrête le polling | — | checklist de complétude affichée | — |

### Scénario 2 — Audit puis décision administrative (validation atomique du score)

**Objectif** : montrer la séparation des responsabilités (auditeur → admin) et la transaction
atomique de calcul du score.
**Acteur déclencheur** : AUDITOR (début), puis ADMIN (décision).
**Participants techniques** : Navigateur ; API (routeurs `audit` puis `admin`) ; service
`app/audit/revue.py`/`opinion.py` ; service `app/admin/review_queue.py` ; moteur
`app/scoring/engine.py` ; PostgreSQL (verrou de ligne) ; file ARQ `arq:queue`.

| # | Émetteur | Destinataire | Action | Données | Résultat | Condition |
|---|---|---|---|---|---|---|
| 1 | AUDITOR | API | `POST /audit/rapports/{id}/reviews` (répété par valeur) | décision par valeur (ACCEPTED/OVERRIDDEN+valeur/NOT_FOUND+motif) | ligne `MetricReview` append-only + mirroir sur la valeur | rapport `IN_AUDIT`, valeur appartient à ce rapport |
| 2 | AUDITOR | API | `POST /audit/rapports/{id}/avis` | décision globale + commentaire si ≠FAVORABLE | `AuditOpinion` inséré, statut → `PENDING_DECISION` | **toutes** les valeurs revues, sinon 422 `revue_incomplete` |
| 3 | API | ADMIN (notification) | Notifications in-app (entreprise + tous les ADMIN actifs) | — | — | — |
| 4 | ADMIN | API | `GET /admin/rapports/{id}/score-verification` (optionnel) | — | couverture actuelle vs. minimum | — |
| 5 | ADMIN | API | `POST /admin/rapports/{id}/valider` | commentaire optionnel | — | statut `PENDING_DECISION` |
| 6 | API | PostgreSQL | `SELECT … FOR UPDATE` sur le rapport | — | ligne verrouillée | re-vérification du statut |
| 7 | API | PostgreSQL | `rapport.status = VALIDATED` (en mémoire, pas encore commité) | — | — | avis d'audit confirmé présent |
| 8 | API | Service scoring | `calculer_score(report_id)` | — | — | — |
| 9 | Service scoring | PostgreSQL | `INSERT … ON CONFLICT DO NOTHING` sur `scoring_configs` (par empreinte SHA-256 du YAML canonique) | contenu YAML de référence | config résolue sans commit intermédiaire | — |
| 10 | Service scoring | PostgreSQL | Lit les valeurs effectives (`audited_value` si OVERRIDDEN, exclue si NOT_FOUND, sinon valeur brute) | — | — | — |
| 11 | Service scoring | (calcul interne) | Moyenne pondérée par pilier puis globale, renormalisée sur les présents | — | score + couverture | **si couverture < seuil minimal de la config (si défini) → exception, rien n'est commité, retour à l'étape 5 avec erreur** |
| 12 | Service scoring | PostgreSQL | `INSERT scores(...)` + `UPDATE esg_reports SET official_score=…, coverage_rate=…, config_hash=…` | — | — | — |
| 13 | API | PostgreSQL | Notification in-app à l'entreprise | — | — | même transaction |
| 14 | API | PostgreSQL | `COMMIT` | — | tout ou rien | — |
| 15 | API | File ARQ `arq:queue` | Enfile `generate_synthesis_pdf` (après commit, best-effort) | `report_id` | — | échec de l'enfilage n'annule jamais la validation déjà commitée |
| 16 | API | Navigateur | 200, rapport `VALIDATED` + score officiel | — | — | — |

### Scénario 3 — Import de positions de portefeuille et consultation de l'empreinte carbone PCAF

**Objectif** : montrer un parcours Investisseur typique, avec validation stricte à l'import et
calcul entièrement à la lecture (pas de job).
**Acteur déclencheur** : INVESTOR.
**Participants techniques** : Navigateur ; API (routeur `investor`) ; service
`app/investor/importation.py` ; service `app/investor/fx.py` ; service `app/investor/carbon.py` ;
moteur pur `app/carbon/pcaf.py` ; PostgreSQL.

| # | Émetteur | Destinataire | Action | Données | Résultat | Condition |
|---|---|---|---|---|---|---|
| 1 | INVESTOR | Navigateur | Choisit un fichier CSV/JSON + valeur totale optionnelle | fichier | — | portefeuille existant vide |
| 2 | Navigateur | API | `POST /portfolios/{id}/positions/import` (multipart, ≤1 Mio) | fichier, `total_value?` | — | — |
| 3 | API | Service import | Détecte le délimiteur, parse chaque ligne | lignes | identifiants normalisés | colonnes autorisées uniquement (`identifier`, `identifier_type`, `outstanding_amount`+`currency` **ou** `weight`, jamais un mélange) |
| 4 | Service import | (validation) | Valide chaque ligne (ISIN/ticker, montant>0 ≤2 décimales, poids quantifié) | — | erreurs par ligne le cas échéant | **toute erreur sur une seule ligne annule tout le fichier** (tout-ou-rien) |
| 5 | Service import | (validation fichier) | Si mode poids : vérifie que la somme ≈1 (±0,001) et qu'un `total_value` est fourni | — | montants dérivés des poids | sinon erreur fichier |
| 6 | Service import | PostgreSQL | Rapproche chaque identifiant contre les entreprises **publiées** | — | `MATCHED`/`UNMATCHED`/`AMBIGUOUS` par ligne | une société non publiée ne doit jamais apparaître comme un « hit » |
| 7 | Service import | Service FX | Convertit chaque montant dans la devise du portefeuille, au taux du jour figé sur la ligne | montant, devise source | `converted_amount`, `fx_rate_used` | — |
| 8 | Service import | PostgreSQL | Si **tout** est valide : insère toutes les positions, `duration_type=OUVERTE`, `start_date=maintenant` | — | commit | sinon aucune ligne n'est écrite |
| 9 | API | Navigateur | Réponse `{imported, matched, unmatched, ambiguous}` | — | — | — |
| 10 | INVESTOR | Navigateur | Ouvre la carte carbone du portefeuille | — | — | — |
| 11 | Navigateur | API | `GET /portfolios/{id}/carbon` | — | — | — |
| 12 | API | PostgreSQL | Lit les positions `ACTIVE` (dates), pour chaque société distincte : son dernier rapport **validé** | — | — | position planifiée/close exclue |
| 13 | API | (calcul) | Valeur effective des émissions par scope (audit appliqué), choix Scope 2 (market-based > non qualifié > location-based) | — | `EmissionsEntreprise` par ligne | — |
| 14 | API | Moteur `pcaf.py` | Facteur d'attribution = montant / EVIC ; émissions financées par scope ; WACI ; qualité de donnée | lignes PCAF | résultat agrégé + par ligne | une ligne sans Scope 1 **ou** 2 → `MISSING_EMISSIONS`, exclue (jamais comptée zéro) ; EVIC absente/≤0 → `MISSING_EVIC` |
| 15 | API | Navigateur | `PortfolioCarbon` (empreinte, WACI, qualité, couvertures, motifs d'exclusion par ligne) | — | — | **aucune écriture en base** — tout est recalculé à chaque appel |

---

## 11. Données pour les diagrammes d'activité

### 11.1 Cycle de vie complet d'un rapport ESG — **swimlanes recommandées**
Acteurs/couloirs : Entreprise, Système (Worker), Auditeur, Administrateur.
- Départ : Entreprise ouvre une session de déclaration.
- Activité : joindre un fichier → (couloir Système) extraction → décision : échec transitoire
  (boucle de reprise ≤3) / échec définitif (fin anticipée `EXTRACTION_FAILED`) / succès.
- Branche : soumis ou non → `AWAITING_ASSIGNMENT` ou retour `DRAFT`.
- (couloir Administrateur) affectation d'un auditeur.
- (couloir Auditeur) boucle « revoir chaque valeur » jusqu'à épuisement de la liste → rendre un
  avis.
- (couloir Administrateur) décision : valider (branche : couverture suffisante → calcul du score,
  sinon blocage et retour) / rejeter / demander une correction.
- Branche correction : retour au couloir Entreprise (nouvelle version) → ré-entre dans le flux au
  niveau « joindre un fichier ».
- États finaux : `VALIDATED` (avec score) ou `REJECTED`.

### 11.2 Inscription et onboarding d'une entreprise — **swimlanes recommandées**
Couloirs : Public (demandeur), Système (e-mail/jetons), Administrateur.
- Départ : soumission du formulaire d'inscription.
- Activité système : génération et envoi du code à 6 chiffres.
- Boucle : vérification du code (jusqu'à 5 tentatives, sinon renvoi obligatoire).
- (couloir Administrateur) consultation facultative du rapport KYC (activité parallèle,
  non bloquante) puis décision à 3 branches : approuver / rejeter / demander une info.
- Branche « demander une info » : retour au couloir Public (réponse) → retour à la décision admin.
- États finaux : `ACTIVE` (avec activation de compte) ou `REJECTED`.

### 11.3 Pipeline d'extraction documentaire — sans swimlane (acteur unique : Worker)
- Départ : job `extract_report` déclenché.
- Garde : statut encore `EXTRACTING` ? sinon fin immédiate (pas d'activité).
- Activités séquentielles : préchauffage embedding → conversion Docling → indexation FAISS →
  recherche sémantique par indicateur → appel LLM (branche : clé réelle vs démo).
- Boucle : second appel groupé pour les codes encore manquants (plafonné à 2 appels LLM au total).
- Activité conditionnelle : relocalisation de page si citation absente (branche : une seule page
  correspondante → promue ; zéro ou plusieurs → valeur écartée).
- Activités parallélisables (conceptuellement, pas confirmées comme threads séparés dans le code) :
  génération des preuves par page.
- Décision finale : échec transitoire (boucle de reprise externe, gérée par ARQ) / échec définitif
  / succès.
- États finaux : `SUCCEEDED` / `FAILED` / `RETRY_SCHEDULED`.

### 11.4 Import de positions de portefeuille — sans swimlane utile (acteur unique : Investisseur,
le reste est système synchrone)
- Départ : téléversement du fichier.
- Activité : détection du délimiteur, lecture ligne à ligne.
- Boucle de validation par ligne avec décision (valide / en erreur) — **toute erreur interrompt
  l'ensemble du traitement** (pas de poursuite partielle, contrairement à 11.5).
- Décision mode montant vs mode poids (exclusifs).
- Activité : rapprochement contre les entreprises publiées, conversion de devise.
- État final : positions créées (succès) ou aucune position créée (échec, rapport d'erreurs par
  ligne).

### 11.5 Validation croisée (import d'un jeu de données externe + corrélation) — sans swimlane
(acteur unique : Chercheur, déclenchant un traitement système)
- Départ : téléversement du CSV externe.
- Boucle par ligne avec décision : identifiant valide et colonne de score présente ? → importée ;
  sinon → **ignorée** (contrairement à 11.4, une ligne invalide ne bloque pas les autres).
- Décision finale sur le fichier entier : au moins une ligne importée ? sinon échec total.
- Activité séparée (à la demande) : rapprochement ISIN puis LEI contre le périmètre du chercheur →
  calcul de Spearman (si ≥3 paires) et de l'écart absolu moyen par pilier.
- État final : rapport de corrélation affiché, liste des non-rapprochées avec motif.

---

## 12. Données pour le diagramme d'architecture

**Flux global** : Navigateur → Frontend (statique, servi séparément) → API `/api/v1` → Services
métier → Base de données / Services externes → réponse (le tout derrière cookie de session, sans
CORS nécessaire en développement car le frontend proxy `/api/v1` en same-origin, `frontend/vite.config.ts`).

| Composant | Responsabilité | Technologies | Communique avec | Protocole / sens |
|---|---|---|---|---|
| Navigateur | Interface utilisateur | React 19.2, react-router-dom 7, TanStack Query 5, client généré Orval (fonctions typées, pas de hooks générés) | API `/api/v1` | HTTPS, cookie de session httpOnly |
| Application racine (`app/main.py`) | Point d'entrée ASGI, santé | FastAPI | API montée, base de données (contrôle de santé uniquement) | — |
| Application API (`api_app`, montée sous `/api/v1`) | Routage, CORS, CSRF, OpenAPI | FastAPI (sous-application complète, schéma OpenAPI propre) | 12 routeurs de domaine, PostgreSQL, Redis, stockage | HTTP interne |
| Services métier (12 modules `app/<domaine>`) | Logique métier par domaine | Python, SQLModel/SQLAlchemy 2 (sessions **synchrones**), Pydantic v2 | PostgreSQL (lecture/écriture), Redis (verrous/débit), stockage (fichiers) | appels de fonction intra-processus |
| PostgreSQL 16 (+ image pgvector) | Persistance relationnelle | `pgvector/pgvector:pg16` | API, Workers | SQL/TCP |
| Redis 7 | Courtier de files ARQ, limites de débit, révocation de session | `redis:7-alpine`, scripts Lua atomiques | API, Workers | TCP |
| Worker par défaut (`WorkerSettings`) | E-mails, synthèse PDF, tâche planifiée de supervision | ARQ, file `arq:queue` (max 10 jobs concurrents) | PostgreSQL, Redis, SMTP, stockage | consommation de file |
| Worker d'extraction (`ExtractionWorkerSettings`) | Pipeline documentaire | ARQ, file `arq:extraction` (max 1 job — un à la fois) ; Docling, PaddleOCR, PyMuPDF, bge-m3 (FlagEmbedding), FAISS, Gemini (`google-genai`) | PostgreSQL, Redis, Gemini, stockage | consommation de file + appel LLM externe |
| Gemini (`gemini-3.6-flash`, repli `gemini-3.5-flash`) | Extraction structurée par LLM | API externe Google | Worker d'extraction uniquement | HTTPS, appel de fonction forcé |
| GLEIF (`api.gleif.org`) | Vérification LEI (KYC) | API externe publique | `app/admin/kyc.py`, `app/company` (vérification en direct) | HTTPS, 5s timeout, pas de redirection suivie |
| SMTP (dev : Mailpit ; prod : serveur réel) | Envoi d'e-mails transactionnels | `smtplib` dans un thread, retries | Worker par défaut | SMTP (starttls/ssl/plain) |
| Stockage fichiers (`STORAGE_PATH`, backend `"local"` uniquement implémenté) | Rapports, preuves, synthèses, avatars, mandats | disque local (monté en volume Docker) | API, Workers | système de fichiers |

**Sécurité transverse** : CORS restreint à une liste blanche explicite (jamais `*` avec
`allow_credentials=True`, levée d'erreur au démarrage sinon) ; middleware CSRF à double soumission
signée (HMAC) ; en-têtes de sécurité (`X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy`, `Cache-Control: no-store` sur `/api/v1`, HSTS en production uniquement — **pas
de Content-Security-Policy constatée**) ; limites de débit par IP/compte sur chaque endpoint public
sensible (compteurs Redis atomiques, échec fermé en cas d'indisponibilité Redre, jamais silencieux).

---

## 13. Données pour le diagramme de composants

**Évaluation de pertinence** : à la granularité « module backend », ce diagramme serait **très
proche du diagramme d'architecture** ci-dessus (chaque module = déjà un composant distinct dans le
tableau précédent). Il n'apporte une valeur distincte que si l'objectif est de montrer les
**dépendances internes entre modules métier** (qui appelle qui, en respectant la règle
architecturale « l'accès inter-domaine ne passe que par les fonctions publiques du module
propriétaire », confirmée dans le code).

Si ce diagramme est retenu, voici les dépendances croisées confirmées (composant → composant
qu'il appelle directement, à l'exclusion des modèles partagés `app/core`) :
- `app/admin` → `app/scoring` (moteur de calcul), `app/audit` (modèles d'avis), `app/company`
  (profil/inscription), `app/investor`/`app/researcher`/`app/institution` (listes de supervision en
  lecture seule).
- `app/reporting`/`app/company` → `app/ingestion` (déclenche le pipeline via la file), `app/worker`
  (enfilage).
- `app/audit` → `app/ingestion` (modèles de valeurs), `app/scoring` (pré-score).
- `app/explainability` → `app/scoring` (décomposition), `app/company`/`app/investor`/
  `app/researcher`/`app/institution` (règles de visibilité par rôle).
- `app/investor` → `app/carbon` (moteur PCAF pur), `app/scoring` (valeur effective).
- `app/researcher` → `app/institution` (réutilise directement `entreprise_perimetre_public` et
  `rattachement_public` depuis `app.institution.router` — import inter-module explicite, pas
  seulement une dépendance de données).
- `app/worker` → `app/ingestion` (import paresseux de la pile d'extraction, uniquement dans le
  worker dédié).

**Recommandation** : signaler ce diagramme comme **potentiellement redondant** avec l'architecture
s'il doit rester à gros grain ; ne le produire que si le rapport/soutenance veut spécifiquement
illustrer cette règle de couplage inter-modules.

---

## 14. Données pour le diagramme de déploiement

| Élément | Déploiement réel |
|---|---|
| Poste utilisateur | Navigateur web standard, aucune contrainte constatée dans le code |
| Frontend | Build Vite statique ; en développement, proxy Vite vers `/api/v1` (same-origin, pas de CORS nécessaire) |
| Image `api` (Dockerfile cible `api`) | FastAPI + migrations + worker par défaut *possible* sur cette même image légère (sans pile ML) ; utilisateur non privilégié `greenfinance` (uid 10001) ; port 8000 exposé |
| Image `worker` (Dockerfile cible `worker`) | Image lourde avec Docling/PaddleOCR/torch/FAISS/bge-m3 ; même utilisateur non privilégié |
| Service `migrate` (docker-compose) | Conteneur **à usage unique**, image `api`, commande `alembic upgrade head`, exécuté avant `api`/`worker` (`depends_on: completed_successfully`) — **les migrations ne sont pas lancées par l'entrypoint de l'image `api` elle-même** |
| Service `api` | Image `api`, `uvicorn … --proxy-headers`, dépend de `db`/`redis` sains + `migrate` terminé |
| Service `worker` | Image **`api`** (légère) exécutant `arq app.worker.settings.WorkerSettings` — confirmant que le worker par défaut tourne sur l'image sans pile ML |
| Service `worker-extraction` | Image `worker` (lourde), `arq app.worker.settings.ExtractionWorkerSettings`, volume supplémentaire `modeles` pour le cache des modèles Hugging Face/Docling |
| Base de données | `pgvector/pgvector:pg16`, volume nommé `pgdata`, non publiée hors développement |
| Cache/files | `redis:7-alpine`, mot de passe obligatoire en production (`--requirepass`), non publiée hors développement |
| Stockage fichiers | Volume nommé `storage` (prod) ou bind-mount local `./storage` (dev) |
| Mailpit | Dev uniquement — capture des e-mails sortants, interface web sur le port 8025 |
| Environnement de production | Overlay `docker-compose.prod.yml` : variables `POSTGRES_PASSWORD`/`REDIS_PASSWORD` obligatoires (échec du démarrage sinon), `ENVIRONMENT=production`, **seul le port de l'API est publié** |
| Reverse proxy | Non présent dans le dépôt lui-même — responsabilité opérationnelle documentée (`FORWARDED_ALLOW_IPS` doit être positionné par l'opérateur pour que les limites de débit par IP lisent la vraie adresse client ; rien dans les fichiers compose ne le fixe) |
| CI (GitHub Actions) | Construit et teste uniquement l'image `api` légère (vérifie explicitement l'absence de `pytest`/`torch`/`docling` dans l'image) ; l'image `worker` n'est **pas construite en CI** |

---

## 15. États et transitions importantes

### 15.1 `Company.status` (RegistrationStatus)

- État initial : `EMAIL_VERIFICATION_PENDING` (créé à l'inscription publique).
- Transitions confirmées : `EMAIL_VERIFICATION_PENDING` → `PENDING_ONBOARDING` (code vérifié) ;
  `PENDING_ONBOARDING` ↔ `INFO_REQUESTED` (demande d'info / réponse) ; `PENDING_ONBOARDING` ou
  `INFO_REQUESTED` → `ACTIVE` (approbation ADMIN) ou → `REJECTED` (rejet ADMIN) ; `ACTIVE` ↔
  `SUSPENDED` (ADMIN) ; `REJECTED` ou `EMAIL_VERIFICATION_PENDING` → `PENDING_ONBOARDING` (réouverture
  automatique sur une ré-inscription aux mêmes identifiants).
- Acteur autorisé : ADMIN pour toutes les transitions de décision ; le titulaire (public, par
  jeton) pour la réponse à une demande d'info et la ré-inscription.
- Transition interdite confirmée : aucune route ne permet de repasser de `ACTIVE` à
  `PENDING_ONBOARDING` sans passer par une suspension explicite ; une entreprise `REJECTED` ne peut
  redevenir active qu'en recommençant tout le cycle (pas de « déblocage » direct constaté).
- Remarque : la valeur par défaut de la colonne au niveau SQLAlchemy est `ACTIVE`
  (`app/company/models.py`), mais **en pratique le code applicatif force toujours
  `EMAIL_VERIFICATION_PENDING` à la création** — le défaut colonne n'est qu'un filet technique, pas
  le comportement observé.

### 15.2 `ESGReport.status` (ReportStatus)

- État initial : `EXTRACTING` par défaut colonne, mais en pratique un rapport est créé en `DRAFT`
  par le service d'ouverture de session.
- Transitions confirmées : `DRAFT` → `EXTRACTING` (fichier joint) → `DRAFT` (si non soumis, analyse
  terminée) ou `AWAITING_ASSIGNMENT` (si déjà soumis) ou `EXTRACTION_FAILED` (échec) ;
  `EXTRACTION_FAILED` → `EXTRACTING` (relance ADMIN) ; `DRAFT` → `AWAITING_ASSIGNMENT` (soumission
  explicite) ; `AWAITING_ASSIGNMENT` → `IN_AUDIT` (affectation) ; `IN_AUDIT` → `PENDING_DECISION`
  (avis rendu) ; `PENDING_DECISION` → `VALIDATED` | `REJECTED` | `REVISION_REQUESTED` ;
  `REVISION_REQUESTED` → (nouvelle ligne, nouvelle version) `EXTRACTING`.
- Transitions interdites confirmées : pas de retour direct de `IN_AUDIT` à `AWAITING_ASSIGNMENT` (la
  ré-affectation n'est pas constatée comme endpoint) ; pas de passage direct de `EXTRACTING` à
  `IN_AUDIT` (l'affectation exige `AWAITING_ASSIGNMENT`) ; `VALIDATED`/`REJECTED` sont terminaux
  pour cette ligne — seule une nouvelle version (nouvelle ligne) permet de continuer après
  `REVISION_REQUESTED`.
- Garde de concurrence : le pipeline d'extraction n'agit que si le statut est encore `EXTRACTING`
  au moment de l'exécution — un job rejoué ne peut jamais faire régresser un rapport déjà avancé.

### 15.3 `ExtractionRun.status`

- Initial : `RUNNING`. Transitions : → `SUCCEEDED` (pipeline terminé) ; → `FAILED` (erreur
  définitive) ; → `RETRY_SCHEDULED` (erreur transitoire, un nouveau `ExtractionRun` sera ouvert à
  la reprise). Aucune transition retour — chaque tentative est une ligne figée (append conceptuel,
  pas de trigger DB confirmé contrairement à `metric_reviews`).

### 15.4 `AccessRequest.status`

- Initial : `PENDING_APPROVAL`. Transitions : → `APPROVED` ou → `REJECTED` (ADMIN uniquement).
  Terminal dans les deux cas pour cette ligne ; une nouvelle demande sur le même e-mail n'est
  possible que si l'ancienne est `REJECTED` (réouverture de la même ligne, pas une nouvelle ligne).

### 15.5 `ESGMetric` / `CarbonEmission` . `review_status` (MetricReviewStatus) — mirroir d'audit

- Initial : `PENDING`. Transitions : → `ACCEPTED` / `OVERRIDDEN` (avec `audited_value` posée) /
  `NOT_FOUND`, chacune déclenchée par une nouvelle ligne `MetricReview` de l'auditeur affecté.
  Rejouer une revue sur la même valeur **ajoute une nouvelle ligne** de journal et met à jour le
  mirroir — le mirroir peut donc changer plusieurs fois, mais chaque changement est tracé de façon
  permanente et non modifiable (déclencheur PostgreSQL empêchant `UPDATE`/`DELETE`/`TRUNCATE` sur
  `metric_reviews`). Transition interdite : revoir une valeur une fois le rapport sorti de
  `IN_AUDIT` (l'avis clôt la revue).

### 15.6 `ResearcherAffiliation.status` (AffiliationStatus)

- Initial : `EN_ATTENTE`. Transitions : → `ACCEPTE` ou → `REFUSE` (RESEARCHER uniquement, une
  seule fois chacune tant que le statut est `EN_ATTENTE`). Une ré-invitation de l'institution
  **réinitialise la même ligne** à `EN_ATTENTE` (pas de nouvelle ligne) — y compris après un
  `REFUSE`.

### 15.7 `Project.status` (ProjectStatus)

- Initial : `OUVERT`. Transition unique et irréversible : → `CLOTURE` (INSTITUTION). Aucune
  réouverture constatée.

### 15.8 `Analysis.status` (AnalysisStatus)

- Initial : `BROUILLON` (valeur par défaut du modèle). Transitions confirmées : `BROUILLON` →
  `SOUMISE` (soumission chercheur) ; `SOUMISE` → `VALIDEE` ou `CORRECTION_DEMANDEE` (décision
  institution) ; `CORRECTION_DEMANDEE` → (nouvelle ligne, version+1) — **le statut initial de cette
  nouvelle ligne n'a pas été confirmé explicitement par la lecture du code de `corriger_analyse` ;
  il est présumé `BROUILLON` par défaut du modèle, à confirmer** (voir §17). `VALIDEE` est
  terminale pour la ligne. Modification du contenu (`modifier_analyse`) possible uniquement tant
  que `BROUILLON`.

### 15.9 Entités sans état persisté (à ne pas modéliser comme machine à états)

- `Portfolio` : pas de statut métier, seulement `archived: bool` (archivé/actif).
- `PortfolioPosition` : pas de colonne de statut ; l'état affiché (`PLANIFIEE`/`ACTIVE`/
  `CLOTUREE`/`ENTREPRISE_SUSPENDUE`) est **recalculé à chaque lecture** à partir des dates et du
  statut de la société — à représenter comme une règle de dérivation, pas comme une vraie machine
  à états en base.

---

## 16. Règles métier importantes

| ID | Règle | Acteurs | Entités | Condition | Comportement attendu | Comportement interdit | Référence |
|---|---|---|---|---|---|---|---|
| RG01 | Aucune valeur extraite n'est stockée sans page de preuve | Système | ESGMetric, CarbonEmission, Evidence | valeur trouvée par le LLM sans `page_source` localisable | valeur écartée | jamais de page devinée/approximée | `app/ingestion/extractor.py:840-848` |
| RG02 | Une seule déclaration active par (société, exercice) | ENTERPRISE/ADMIN | ESGReport | création d'une nouvelle session | refusée si une déclaration active existe déjà ou si l'exercice est déjà validé | — | `app/company/rapports.py:115-147` |
| RG03 | Un seul brouillon/non-soumis par (société, exercice, type) | Système | ESGReport | — | index unique partiel `submitted_at IS NULL` | — | `app/ingestion/models.py:61-68` |
| RG04 | `metric_reviews` est strictement append-only | Système (PostgreSQL) | MetricReview | toute tentative UPDATE/DELETE/TRUNCATE | exception levée par déclencheur | aucune modification possible, même par un administrateur | migration `e3b8c5d1f9a2` |
| RG05 | Séparation des responsabilités de l'audit | AUDITOR, ADMIN | ESGReport, MetricReview, AuditOpinion | — | seul l'auditeur affecté revoit/opine, et seulement en `IN_AUDIT` ; l'admin ne fait que lire le journal | l'admin ne peut jamais écrire une revue | `app/audit/revue.py`, `app/admin/router.py:553-566` |
| RG06 | Pré-score masqué avant l'avis | AUDITOR | ESGReport | statut encore `IN_AUDIT` | 409 `avis_requis` | le chiffre ne doit jamais influencer la revue | `app/audit/revue.py:120-143` |
| RG07 | Avis d'audit complet obligatoire | AUDITOR | ESGMetric, CarbonEmission, AuditOpinion | une valeur encore `PENDING` | 422 `revue_incomplete`, avis refusé | — | `app/audit/opinion.py:49-56` |
| RG08 | Validation verrouillée et vérifiée | ADMIN | ESGReport | décision de valider | `SELECT…FOR UPDATE` + re-vérification du statut + avis existant | aucune validation sans verrou | `app/admin/review_queue.py:267-289` |
| RG09 | Score et configuration figés par empreinte | Système | ScoringConfig, Score | calcul d'un score | SHA-256 du contenu YAML canonique ; un ancien score se recalcule toujours à l'identique | une modification de méthodologie ne modifie jamais un score déjà publié | `app/scoring/config_schema.py:95-103` |
| RG10 | Couverture minimale (si définie) bloque la validation | Système | ESGReport, ScoringConfig | `coverage_rate < min_coverage` | exception, rien n'est commité | — **mécanisme présent mais dormant** : `config/weights/default.yaml` ne fixe pas `min_coverage` aujourd'hui | `app/scoring/engine.py:303-308` |
| RG11 | Renormalisation des indicateurs/piliers absents | Système | Score | un indicateur ou pilier absent du rapport | poids exclu du calcul (numérateur et dénominateur), jamais remplacé par zéro | — | `app/scoring/engine.py:140-157, 264-285` |
| RG12 | PCAF : Scope 3 jamais sommé aux Scopes 1+2 | Système | CarbonEmission | calcul des émissions financées | champs séparés tout au long du calcul | — | `app/carbon/pcaf.py:141-153` |
| RG13 | PCAF : donnée manquante = exclusion, jamais zéro | Système | CarbonEmission, PortfolioPosition | Scope 1 ou 2 absent, ou EVIC absente/≤0 | ligne exclue avec motif (`MISSING_EMISSIONS`/`MISSING_EVIC`), comptée dans la couverture | jamais traitée comme une émission nulle | `app/carbon/pcaf.py:124-134` |
| RG14 | Journal d'audit de compte scopé aux événements de compte/session | Système | AuditLogEntry | validation/rejet/correction d'un rapport | **aucune** ligne `AuditLogEntry` écrite pour ces décisions (choix de conception explicite en commentaire de code) | ne pas s'attendre à une trace `AuditLogEntry` pour toute action métier | `app/admin/review_queue.py:541` (commentaire) |
| RG15 | Comparaison investisseur plafonnée | INVESTOR | Company | sélection de plus de 4 entreprises | 422 `comparaison_trop_large` | — | `app/investor/entreprises.py:270-287` |
| RG16 | Import de portefeuille strictement tout-ou-rien | INVESTOR | PortfolioPosition | au moins une ligne en erreur | aucune ligne écrite, rapport d'erreurs par ligne | pas d'import partiel | `app/investor/importation.py:278-285` |
| RG17 | Import de jeu de référence (chercheur) : partiel, tolérant | RESEARCHER | ReferenceDatasetRow | une ligne invalide | ligne ignorée, import des autres lignes poursuivi | échec total seulement si **zéro** ligne importée | `app/researcher/cross_validation.py:220-225` |
| RG18 | Rapprochement de portefeuille contre les entreprises publiées uniquement | Système | PortfolioPosition, Company | import | une société non publiée ne peut jamais produire un `MATCHED` | ne jamais révéler l'existence d'une société non publiée via l'import | `app/investor/importation.py:182-191` |
| RG19 | Périmètre institution/chercheur = union des périmètres de projets | INSTITUTION, RESEARCHER | ProjectCompany | consultation d'une fiche entreprise/preuve | restreint à l'union des périmètres de tous les projets de l'acteur | le catalogue de **liste** reste non filtré pour l'institution (volontaire) | `app/institution/projets.py:172-184`, `app/researcher` |
| RG20 | Document de projet = rapport actuellement publié uniquement | INSTITUTION | ProjectDocument | ajout d'un document | le rapport doit être le dernier validé et publié de l'entreprise | un rapport supplanté ne peut plus être attaché | `app/institution/projets.py:266-271` |
| RG21 | Brouillon d'analyse invisible à l'institution | INSTITUTION | Analysis | toute tentative d'accès | 404 identique, qu'elle n'existe pas ou soit un brouillon | jamais un 403 qui révélerait son existence | `app/institution/analyses.py:43-62` |
| RG22 | Quota d'export fini, côté institution uniquement | INSTITUTION | InstitutionProfile | export d'une analyse | décrémenté avant écriture, bloqué à 0 | aucun mécanisme de réapprovisionnement constaté dans ce périmètre ; aucun quota équivalent côté chercheur | `app/institution/analyses.py:148-161` |
| RG23 | Snapshot figé d'une entreprise dans une analyse | RESEARCHER | AnalysisCompany | ajout d'une entreprise à une analyse | `report_id`/`score_id` figés à cet instant | une republication ultérieure ne modifie jamais une analyse existante | `app/researcher/models.py:70-82` |
| RG24 | Règle 403 vs 404 uniforme | Système | toutes | accès à une ressource | rôle non autorisé → 403 ; bon rôle mais hors périmètre → 404 identique à « inexistant » | ne jamais révéler l'existence d'une ressource hors périmètre | `README.md:77-79`, confirmé module par module |
| RG25 | Mot de passe : 12 caractères minimum, 72 octets UTF-8 maximum | tous (activation/réinitialisation/changement) | User | définition d'un nouveau mot de passe | rejet si hors bornes | ne s'applique jamais rétroactivement à un mot de passe existant | `app/auth/schemas.py:27-50` |
| RG26 | Limites de débit, échec fermé | Système | — | Redis indisponible | 503 explicite | jamais un contournement silencieux | `app/auth/rate_limit.py:12-16` et équivalents |
| RG27 | Protection anti-SSRF sur l'import par URL | ENTERPRISE/ADMIN | ESGReport | `POST /company/rapports/import-url` | IP publique uniquement, redirections revalidées (max 2), 50 Mo, 60 s au total | fenêtre résiduelle de « DNS rebinding » documentée comme non fermée, pas cachée | `app/company/url_fetch.py` |
| RG28 | Validation ISIN/LEI par chiffre de contrôle | Système | Company, PortfolioPosition, ReferenceDatasetRow | tout identifiant fourni | Luhn (ISIN) / ISO 7064 MOD 97-10 (LEI) | jamais accepté sur la seule forme regex | `app/company/identifiers.py` |

---

## 17. Incohérences et zones d'incertitude

**A. Documentation cible obsolète par rapport au code actuel** (`docs/ARCHITECTURE.md`,
`docs/WORKFLOWS.md` — marqués « PROPOSED TARGET », vérifiés indépendamment) :
1. Le tableau `companies` du §3.1 du doc est annoté « *Current:* `entreprise` (nom, secteur, pays,
   actif, date_publication…). No ISIN, LEI… » — **faux aujourd'hui** : la table s'appelle déjà
   `companies`, `isin`/`lei` existent déjà (`app/company/models.py:62-63`), et `published_at` est
   déjà le nom anglais utilisé. Cette note décrit un état antérieur à la tâche 1.1, déjà dépassé.
2. La liste des valeurs de `RegistrationStatus` au §3.1 du doc omet `EMAIL_VERIFICATION_PENDING`
   (ajouté par la toute dernière migration de la chaîne, tâche 5.11).
3. Le doc omet entièrement de son tableau `companies` : `tax_id`/`tax_id_type`, `logo`,
   `description`, `website`, `minimum_investment_amount`/`_currency`, `ticker`.
4. Le doc affirme `esg_reports.official_score`/`coverage_rate` typés `numeric(5,2)`/`numeric(5,4)`
   — en réalité ce sont des `float` Python simples, **sans aucune contrainte CHECK de plage en
   base** (contrairement à `Score.global_score` qui, lui, a bien un CHECK).
5. Le doc mentionne une colonne `proof_page` sur `esg_metrics` — elle n'existe pas ; la page vit sur
   `Evidence.page_start`/`page_end`, atteinte via `ESGMetric.proof_id`.
6. Le doc affirme qu'il n'existe « aucune unicité sur (rapport_id, code) » — **faux aujourd'hui** :
   la contrainte `uq_esg_metrics_report_metric_code` existe bel et bien.
7. Le §3.7 du doc omet `metric_reviews` (couvert correctement ailleurs dans le même doc, §3.3),
   `access_requests`, `reference_datasets`/`reference_dataset_rows`, et les tables de jetons
   d'authentification, de sa section consacrée au modèle de domaine.
8. §1.3 du doc (workflow) : l'ordre narré (calculer le score **puis** passer le statut à
   `VALIDATED`) est inversé par rapport au code réel (le statut est posé **avant** l'appel au
   calcul). Sans conséquence sur l'atomicité (rien n'est commité avant la fin), mais à corriger si
   un diagramme de séquence suit le texte du doc au lieu du code.
9. §1.3 du doc affirme que la transaction de validation « écrit l'entrée du journal d'audit » — le
   code ne le fait jamais pour validation/rejet/correction (choix de conception explicite en
   commentaire, RG14). Le journal **est** utilisé pour la soumission, mais pas pour la décision.
10. §6 du doc (diagramme ASCII) liste `recompute_portfolio(portfolio_id)` comme un job — ce job
    **n'existe pas** dans le code (confirmé par lecture intégrale de `app/worker/jobs.py` et par
    recherche globale). Le texte du même paragraphe du doc l'admet d'ailleurs lui-même. Toutes les
    figures de portefeuille/carbone sont calculées à chaque lecture.
11. §2.1 du doc (workflow investisseur) propose une machine à états
    `EMPTY→IMPORTED→MATCHED→COMPUTING→COMPUTED/STALE` — **aucune colonne de statut de ce type
    n'existe** sur `Portfolio` ou `PortfolioPosition`. Seuls existent `archived: bool` et un état
    de présentation recalculé (`EtatPosition`, non persisté).
12. §3.1/§3.2 du doc (configuration YAML personnalisée par chercheur, recalcul par lot) : aucune
    route, aucun routeur `app/scoring/router.py` n'existe. Le modèle de données est prêt
    (`ScoringConfig.owner_user_id` nullable) mais rien ne l'exploite — **cohérent avec le doc
    lui-même**, qui ne marque ces sous-sections d'aucune mention « implémenté en tâche X »
    (confirmation, pas contradiction, mais à ne pas présenter comme existant dans un diagramme).
13. §8 du doc affirme que « le conteneur exécute `alembic upgrade head` (ou un service `migrate`
    ponctuel) » — seule la seconde moitié est vraie : aucune image ne lance les migrations depuis
    son propre `CMD`/entrypoint ; c'est exclusivement le service `migrate` ponctuel qui le fait.
14. Les noms d'étapes du Dockerfile diffèrent du raccourci du doc (`builder`→`api`/`worker`) :
    réellement `construction-api`, `construction-worker`, `execution`, `api`, `worker` — différence
    de forme, pas de fond.

**B. Zones ambiguës dans le schéma de données** (ne pas trancher la nature UML sans confirmation
humaine, cf. règle « ne pas deviner ») :
15. `PortfolioPosition.company_id` : FK nullable avec `ON DELETE CASCADE` — combinaison inhabituelle
    (`SET NULL` serait attendu pour préserver une position comme « non rapprochée » si l'entreprise
    est supprimée). Le code ne documente que la nullabilité, pas ce choix de cascade précis.
16. `Evidence` partagée par plusieurs valeurs (`ESGMetric`/`CarbonEmission`) avec cascade **depuis**
    les valeurs vers la preuve : supprimer une preuve supprime toutes les valeurs qui la citent. Le
    degré réel de partage (une page = une valeur, ou une page = plusieurs valeurs en pratique) n'a
    pas été mesuré dans le code lu, seulement rendu possible par le modèle.
17. Quatre énumérations (`KycCheckResult`, `BaselineScope`, `ComparedScore`, `UnmatchedReason`)
    n'ont été reliées à **aucune** colonne persistée dans les dix fichiers `models.py` lus — usage
    probable limité aux schémas de requête/réponse ou à des calculs à la volée, mais non confirmé
    formellement à 100 %.
18. `AnalysisStatus` de la nouvelle ligne créée par `corriger_analyse` : présumé `BROUILLON` (valeur
    par défaut du modèle) mais non confirmé explicitement par une lecture directe de cette
    assignation dans le code (voir §15.8).

**C. Zones nécessitant une confirmation humaine, hors périmètre du code seul :**
19. **Workflow du système existant (section 6)** : aucune description d'un processus antérieur
    (manuel ou autre) n'existe dans ce dépôt. Si un diagramme de ce type est réellement requis pour
    le rapport/la soutenance, l'information doit venir d'une source externe au code (porteur de
    projet, cahier des charges) — ce document s'abstient volontairement de l'inventer.
20. `GET /auth/avatars/{user_id}/{file}` exige seulement une session valide, **pas** la propriété
    de l'avatar demandé — tout utilisateur authentifié peut donc consulter l'avatar de n'importe
    quel autre utilisateur en connaissant/devinant son identifiant. C'est un constat de code, pas
    une affirmation sur une intention de conception ; à signaler sans le qualifier de « bug » ou de
    « feature » sans confirmation.
21. Deux styles d'URL coexistent dans l'espace investisseur : routes françaises
    `/investor/portefeuilles/...` et routes anglaises `/portfolios/{id}/carbon`,
    `/portfolios/{id}/positions/import` — cohérent avec un renommage français→anglais en cours par
    ailleurs dans le projet (mentionné par `docs/RENAME_PLAN.md`, non lu dans cette analyse), mais
    à vérifier si un diagramme de cas d'utilisation doit refléter un seul style d'URL ou les deux.
22. Dépendance frontend `@tremor/react` présente dans `package.json` mais non observée utilisée
    dans les ~15 fichiers de page/composant lus — possiblement un reliquat, non confirmé.
23. Dépendance frontend `playwright` présente sans fichier de spécification e2e trouvé sous
    `frontend/src` — possiblement utilisée ailleurs dans l'arborescence (non vérifié) ou inutilisée.
24. Les conventions de code détaillées des fichiers racine `ARCHITECTURE.md` et
    `FRONTEND-ARCHITECTURE.md` (mentionnés par le README comme les conventions **actuelles**
    contraignantes, par opposition à `docs/ARCHITECTURE.md` qui est la cible) n'ont pas été lus
    dans cette passe de recherche — à consulter si le diagramme de composants (section 13) doit
    être approfondi.

---

## 18. Liste recommandée des diagrammes

| Diagramme | Données disponibles | Pertinence rapport | Pertinence soutenance | Priorité | Remarques |
|---|---|---|---|---|---|
| Workflow système existant | **Insuffisant** (aucune source dans le dépôt) | Non, sauf source externe obtenue | Non | Faible | Nécessite une confirmation humaine (§17-C19) avant toute production |
| Workflow système proposé | Complet | Oui | Oui | Haute | Section 7 ; plusieurs sous-workflows (inscription, rapport, portefeuille, recherche) |
| Diagramme de classes | Complet | Oui | Oui | Haute | 29 entités, relations classifiées, 2 points ambigus signalés (§17-B) |
| Cas d'utilisation général | Complet | Oui | Oui | Haute | 7 acteurs (incl. Public) |
| Cas d'utilisation détaillé | Complet | Oui | Oui | Haute | include/extend justifiés uniquement quand la logique le permet |
| Séquence 1 — Dépôt & extraction | Complet | Oui | Oui | Haute | Montre le pipeline IA, le plus distinctif du projet |
| Séquence 2 — Audit & validation atomique | Complet | Oui | Oui | Haute | Montre la transaction et la séparation des responsabilités |
| Séquence 3 — Import portefeuille & PCAF | Complet | Oui | Oui | Moyenne | Montre un parcours « lecture pure », complémentaire des deux premiers |
| Activité — Cycle de vie du rapport | Complet | Oui | Oui | Haute | Swimlanes recommandées (4 acteurs) |
| Activité — Inscription/onboarding | Complet | Oui | Oui | Moyenne | Swimlanes recommandées (3 acteurs) |
| Activité — Pipeline d'extraction | Complet | Oui | Non (trop technique pour une soutenance orale) | Moyenne | Acteur unique, pas de swimlane nécessaire |
| Activité — Import portefeuille / validation croisée | Complet | Oui | Non | Faible | Utile en annexe de rapport seulement |
| Architecture | Complet | Oui | Oui | Haute | Un seul diagramme suffit (flux + composants techniques) |
| Composants | Partiel, **redondant si gros grain** | Possible | Non | Faible | À ne produire que pour illustrer la règle de couplage inter-modules (§13) |
| Déploiement | Complet | Oui | Oui | Moyenne | Topologie Docker Compose dev/prod bien documentée |
| États/transitions (hors catégorie demandée mais fourni) | Complet | Oui | Oui | Haute | 8 machines à états réelles identifiées (§15) |

---

## 19. Ordre recommandé de génération future

1. Diagramme de classes (fondation de tout le reste — toutes les entités/relations sont déjà
   stabilisées section 8).
2. Cas d'utilisation général, puis détaillés (s'appuient directement sur les acteurs/section 4 et
   les fonctionnalités/section 5).
3. Workflow du système proposé (section 7) — avant les séquences, car il donne le squelette des
   trois scénarios choisis.
4. Les 3 diagrammes de séquence (section 10) — réutilisent directement le workflow ci-dessus, à un
   niveau de détail technique supérieur.
5. Diagrammes d'activité (section 11) — en particulier le cycle de vie du rapport et
   l'inscription/onboarding, qui bénéficient des swimlanes déjà identifiées.
6. Diagramme d'architecture (section 12) — peut être produit en parallèle des étapes 1 à 5, sans
   dépendance forte.
7. Diagramme de déploiement (section 14) — dépend de l'architecture logique ci-dessus.
8. Diagramme de composants (section 13) — seulement si jugé non redondant après production de
   l'architecture ; sinon, l'omettre.
9. Workflow du système existant — **seulement si** une source externe est obtenue (§17-C19) ; sinon
   l'omettre du livrable plutôt que l'inventer.

Adaptation suggérée par rapport à l'ordre générique proposé dans la consigne : les cas d'utilisation
ont été avancés avant le détail du workflow proposé car, dans ce projet, les acteurs et les
fonctionnalités (sections 4-5) sont plus immédiatement stables que le séquencement fin de chaque
workflow, et donnent une meilleure charpente pour vérifier ensuite la cohérence des séquences.

---

## Annexe — Sources

Fichiers de recherche intermédiaires (lecture intégrale du code source, non diagrammatiques,
conservés comme preuve de traçabilité) :
- Modèles de données & migrations Alembic (47 révisions, chaîne linéaire confirmée)
- `app/auth`, `app/admin`, `app/company`, `app/access_requests`, `app/contact` (+ dépendances
  `app/core`)
- `app/reporting`, `app/ingestion`, `app/audit`, `app/scoring`, `app/explainability`, `app/carbon`,
  `config/weights/default.yaml`
- `app/investor`, `app/institution`, `app/researcher`, `config/fx/`
- `app/worker`, `app/core/config.py`, Dockerfile, docker-compose (×3), `.github/workflows/ci.yml`,
  `pyproject.toml`, `scripts/dev-up.sh`, `scripts/seed_demo.py`
- `frontend/src` (routes, navigation, client API généré, workflows UI tracés), `package.json`,
  `frontend/vite.config.ts`, `frontend/orval.config.ts`

Documents projet utilisés comme hypothèses de travail, puis vérifiés indépendamment dans le code :
`README.md`, `docs/ARCHITECTURE.md`, `docs/WORKFLOWS.md`. Non lus dans cette passe (à consulter si
approfondissement nécessaire) : `ARCHITECTURE.md` (racine), `FRONTEND-ARCHITECTURE.md`,
`docs/RENAME_PLAN.md`, `docs/TASKS.md`.
