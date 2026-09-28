# Pages publiques et envoi d'e-mails

Les pages `/login`, `/mot-de-passe-oublie`, `/reinitialiser-mot-de-passe?token=…`
et `/contact` sont accessibles sans compte. Le rôle est toujours déterminé par le serveur.

## Configuration SMTP

Renseigner les variables suivantes dans l'environnement du serveur, puis redémarrer l'API :

| Variable | Usage |
| --- | --- |
| `SMTP_HOST` | Adresse du relais SMTP |
| `SMTP_PORT` | Port du relais, `587` par défaut |
| `SMTP_SECURITY` | `starttls` par défaut, `ssl` pour TLS dès la connexion, `plain` uniquement en développement |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Identifiants du relais ; tous deux vides si le relais local ne demande pas d'authentification |
| `SMTP_TIMEOUT_SECONDS` | Délai maximal par opération réseau, 10 secondes par défaut |
| `MAIL_FROM` | Adresse d'expédition autorisée par le relais, sans nom d'affichage |
| `CONTACT_TO_EMAIL` | Adresse de l'équipe qui reçoit les demandes de contact |
| `FRONTEND_BASE_URL` | Origine du frontend utilisée pour construire les liens de réinitialisation ; HTTPS en production |

Les certificats TLS sont vérifiés. `SMTP_SECURITY=plain` bloque le démarrage en production.
Il n'y a aucun envoi d'e-mail configuré par défaut : l'API peut démarrer et les autres parcours
restent utilisables, mais le contact et la demande de réinitialisation répondent `503` tant que
leurs paramètres obligatoires manquent. Les liens de réinitialisation ne sont plus écrits dans
les journaux. Pour le développement, un relais SMTP local de capture peut être configuré avec
`SMTP_SECURITY=plain` et sans identifiants. Ne jamais ajouter de véritables secrets dans Git.

## Contrats et comportement

- `POST /api/v1/contact` (`sendContactMessage`) : corps `{nom, email, sujet, message}`.
  Les espaces aux extrémités sont supprimés. Nom : 2–100 caractères ; sujet : 3–150,
  sur une ligne ; message : 20–5 000 ; e-mail valide, 254 caractères au maximum.
  Le destinataire est uniquement `CONTACT_TO_EMAIL` ; l'adresse du visiteur sert de `Reply-To`.
  `204` signifie que le relais SMTP a accepté le message. Une erreur de configuration,
  de connexion ou un refus SMTP produit `503` ; aucune confirmation trompeuse n'est renvoyée.
- Contact : trois demandes par heure et par IP, puis `429`. Le compteur et son expiration
  Redis sont atomiques. Une panne Redis produit `503`. Seule l'adresse client ASGI est
  utilisée, jamais directement un en-tête fourni par le visiteur. Derrière un proxy, configurer
  la liste des proxys de confiance du serveur ASGI ; ne pas autoriser arbitrairement toutes
  les origines des en-têtes transférés.
- `POST /api/v1/auth/mot-de-passe-oublie` conserve la réponse générique `204` pour un compte
  actif, inconnu ou désactivé. La configuration SMTP est vérifiée **avant** la recherche de
  compte : une configuration absente donne le même `503` pour toutes les adresses. Le quota
  existant de trois demandes par adresse et par heure reste en place, y compris pour les
  adresses inconnues.
- Pour un compte actif, l'envoi du lien s'exécute après la réponse HTTP via `BackgroundTasks`.
  Une panne du relais ne change pas la réponse et ne révèle pas les comptes. Seul le type
  d'erreur est journalisé ; ni adresse, ni corps de message, ni jeton. Ces tâches en mémoire
  n'ont pas de reprise automatique : un arrêt du processus ou une panne SMTP peut empêcher
  l'envoi ; une nouvelle demande reste nécessaire. Le relais peut également accepter un
  message qui sera ensuite rejeté ou classé comme indésirable par le destinataire.
- `POST /api/v1/auth/reinitialiser-mot-de-passe` consomme le jeton à usage unique, valable
  30 minutes, et révoque les sessions existantes. Le nouveau mot de passe exige au moins
  8 caractères et au plus 72 octets UTF-8, limite de bcrypt ; ses espaces sont conservés.

## Vérification

Les tests SMTP utilisent des doubles de test ; aucun e-mail réel n'est envoyé. Les tests de
contact couvrent la validation, le quota, les en-têtes transférés falsifiés et les pannes.
Les tests de réinitialisation vérifient aussi l'absence du jeton dans les réponses/journaux,
la réponse générique lors d'un échec SMTP et l'indisponibilité uniforme sans configuration.
