# Matrice des permissions — GreenFinance Scorer

Générée le 2026-09-10 par lecture directe des routes (`app/*/router.py`), pas écrite à la main :
chaque ligne reprend le `require_role(...)` réellement posé en `Depends()` sur la route, et le
filtre de portée des données réellement appliqué dans le handler ou le service qu'il appelle.
À régénérer (ou au moins revérifier) chaque fois qu'une route est ajoutée ou modifiée — c'est un
reflet du code, pas une spécification indépendante de lui.

Convention : « Portée » décrit sur quelles lignes de la table concernée l'action s'applique,
« Statut requis » décrit une précondition sur `StatutRapport` (ou l'équivalent) vérifiée par le
service métier avant d'autoriser l'action — au-delà du simple contrôle de rôle.

## Espace Auth (`app/auth/router.py`)

| Route | Rôle exigé | Portée | Remarque |
|---|---|---|---|
| `POST /auth/login` | Aucun (pré-authentification) | — | Rate-limité par e-mail (`app/auth/rate_limit.py`) |
| `POST /auth/logout` | Tout utilisateur authentifié | Sa propre session | Révoque toutes les sessions de l'utilisateur |
| `GET /auth/me` | Tout utilisateur authentifié | Son propre compte | — |
| `POST /auth/changer-mot-de-passe` | Tout utilisateur authentifié | Son propre compte | Révoque puis rouvre sa propre session |

## Espace Administrateur (`app/admin/router.py`)

Toutes les routes ci-dessous exigent `Role.ADMINISTRATEUR` — aucune exception.

| Route | Portée | Statut requis |
|---|---|---|
| `GET /admin/utilisateurs` | Comptes actifs (ou tous, si `inclure_inactifs`) d'un rôle donné | — |
| `POST /admin/utilisateurs` | Création — refuse `role=ADMINISTRATEUR` (aucune route ne permet de créer un autre admin) | — |
| `POST /admin/utilisateurs/{id}/desactiver` | Un compte, quel que soit son rôle | — |
| `POST /admin/utilisateurs/{id}/reactiver` | Un compte, quel que soit son rôle | — |
| `POST /admin/utilisateurs/{id}/role` | Un compte, quel que soit son rôle | — |
| `GET /admin/rapports/a-affecter` | Tous les rapports (dérivé : `EN_EXTRACTION` + extraction terminée) | — |
| `POST /admin/rapports/{id}/affecter` | Un rapport, toutes entreprises | Doit être en file « à affecter » |
| `GET /admin/rapports/en-validation` | Tous les rapports (dérivé : `EN_VALIDATION` + avis déjà rendu) | — |
| `GET /admin/rapports/{id}` | Un rapport, toutes entreprises, tout statut | — |
| `GET /admin/rapports/{id}/fichier` | Le PDF original, toutes entreprises | — |
| `GET /admin/rapports/{id}/versions` | Chaîne de versions d'un rapport | — |
| `GET /admin/rapports/{id}/avis` | Avis rendus sur un rapport | — |
| `POST /admin/rapports/{id}/valider` | Un rapport | `EN_VALIDATION` + avis présent |
| `POST /admin/rapports/{id}/rejeter` | Un rapport | `EN_VALIDATION` + avis présent |
| `POST /admin/rapports/{id}/demander-correction` | Un rapport | `EN_VALIDATION` + avis présent |
| `GET /admin/entreprises` | Toutes les entreprises | — |
| `GET /admin/entreprises/publiables` | Entreprises avec ≥1 rapport `VALIDE`, non publiées | — |
| `POST /admin/entreprises/{id}/publier` | Une entreprise | ≥1 rapport `VALIDE` |
| `POST /admin/entreprises/{id}/suspendre` | Une entreprise | — |
| `POST /admin/entreprises/{id}/reactiver` | Une entreprise | — |
| `GET /admin/entreprises/{id}/rapports` | Rapports d'une entreprise | — |
| `GET /admin/journal-audit` | Journal des événements de compte/session (pas encore les transitions métier — voir constat §5) | — |
| `GET /admin/dashboard` | Indicateurs agrégés | — |

## Espace Auditeur (`app/audit/router.py`)

Toutes les routes exigent `Role.AUDITEUR`. **Portée systématiquement filtrée sur
`auditeur_id == current_user.id`** — un auditeur ne voit jamais un dossier affecté à un autre.

| Route | Portée | Statut requis |
|---|---|---|
| `GET /audit/rapports` | Ses dossiers affectés | `AFFECTE_AUDITEUR` |
| `GET /audit/rapports/{id}` | Un dossier qui lui est affecté (tout statut — peut rouvrir après avis) | — |
| `GET /audit/historique` | Ses propres avis déjà rendus | — |
| `POST /audit/rapports/{id}/avis` | Un dossier qui lui est affecté | Fait passer le rapport en `EN_VALIDATION` |

Aucune route de ce module n'écrit `StatutRapport.VALIDE`/`REJETE`/`DEMANDE_CORRECTION` — l'Auditeur
recommande (`DecisionAudit`), il ne décide jamais.

## Espace Entreprise (`app/company/router.py`)

Toutes les routes exigent `Role.ENTREPRISE`. **Portée systématiquement filtrée sur
`entreprise_id == current_user.entreprise.id`** (`_entreprise_id()`, `app/company/router.py:28-33`)
— un compte Entreprise sans profil `Entreprise` rattaché reçoit `entreprise_non_rattachee` sur
toute action.

| Route | Portée | Statut requis |
|---|---|---|
| `GET /company/rapports` | Ses propres rapports | — |
| `POST /company/rapports` | Dépôt pour sa propre entreprise | Entreprise non suspendue, fichier non déjà déposé (checksum) |
| `POST /company/rapports/{id}/corrections` | Nouvelle version d'un de ses rapports | Le rapport précédent doit être `DEMANDE_CORRECTION` |
| `GET /company/rapports/{id}` | Un de ses rapports (404, jamais 403, si ce n'est pas le sien — n'expose pas l'existence d'un rapport d'autrui) | — |

Aucune route de ce module n'écrit un statut de décision — l'Entreprise ne valide jamais son propre
rapport.

## Ce que cette matrice confirme

- Le contrôle est posé sur **chaque** route via `Depends(require_role(...))`
  (`app/auth/permissions.py`) — jamais dans le composant React, conformément à l'exigence du
  cahier des charges §3.
- La séparation Auditeur (recommande) / Administrateur (décide et publie) / Entreprise (dépose,
  ne valide pas) est vérifiable route par route : aucun chevauchement trouvé.
- La portée « sur quelles données » est un filtre applicatif par requête (`auditeur_id ==`,
  `entreprise_id ==`), jamais une politique déclarative centralisée — un futur endpoint qui
  oublierait ce filtre ne serait pas intercepté ailleurs.

## Ce qui manque encore (voir la radiographie complète pour le détail)

- Aucune route pour Investisseur, Chercheur, Institution (§11) — trois routers montés, zéro route.
- Aucune route de lecture/marquage des notifications (§10).
- Le filtre « sur quelles données » n'est testé par aucun test dédié à l'accès croisé
  (« un Auditeur B ne peut pas voir un dossier affecté à l'Auditeur A ») — à ajouter (§13).
