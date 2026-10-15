# Procédure : demandes d'exercice des droits RGPD

La plateforme n'offre pas encore d'export ni de suppression de compte en libre-service. Une demande
d'accès, de portabilité ou d'effacement est donc traitée à la main par l'exploitant, avec les
commandes ci-dessous, **dans le délai d'un mois** (RGPD, art. 12.3). La politique de confidentialité
(`/confidentialite`) indique l'adresse à laquelle ces demandes arrivent.

Toutes les commandes se lancent sur la VM, depuis le dossier du dépôt :

```bash
PROD="-f docker-compose.yml -f docker-compose.prod.yml"
PSQL="docker compose $PROD exec -T db psql -U greenfinance -d greenfinance"
```

## 1. Vérifier l'identité du demandeur

Répondre uniquement à une demande envoyée depuis l'adresse e-mail du compte, ou après une
vérification équivalente. Noter la date de réception.

## 2. Retrouver le compte

```bash
$PSQL -c "select id, email, name, role, active, created_at from users where email = lower('personne@exemple.org');"
```

Dans la suite, `<ID>` est l'`id` obtenu.

## 3. Droit d'accès et portabilité : export JSON

```bash
$PSQL -At -c "
select json_build_object(
  'compte', (select row_to_json(u) from (select id, email, name, role, active, created_at, activated_at from users where id = '<ID>') u),
  'entreprise', (select row_to_json(c) from (select id, name, sector, country, website, lei, isin, status, registered_at from companies where owner_user_id = '<ID>') c),
  'demandes_acces', (select coalesce(json_agg(a), '[]') from (select * from access_requests where user_id = '<ID>') a),
  'portefeuilles', (select coalesce(json_agg(p), '[]') from (select * from portfolios where user_id = '<ID>') p),
  'notifications', (select coalesce(json_agg(n), '[]') from (select type, message, sent_at, read from notifications where user_id = '<ID>') n),
  'journal_connexions', (select coalesce(json_agg(l), '[]') from (select action, resource_type, result, occurred_at from audit_log where actor_id = '<ID>') l)
);" > export-<ID>.json
```

Envoyer le fichier au demandeur par un canal sûr, puis le supprimer de la VM. Si le compte a déposé
des fichiers (photo de profil, lettre de mandat, rapports), les joindre depuis le volume `storage` :
leur chemin relatif est dans `users.avatar_path`, `companies.mandate_letter_path` et
`esg_reports.source_file`.

## 4. Droit à l'effacement

### 4.1 Effacement possible ou anonymisation ?

Certaines données sont des pièces du dossier d'audit et de recherche, liées au compte par des clés
étrangères `RESTRICT` : un avis d'auditeur, une revue d'indicateur, une analyse ou un projet de
recherche, une configuration de score. Les compter :

```bash
$PSQL -c "
select (select count(*) from analyses where researcher_id = '<ID>')        as analyses,
       (select count(*) from audit_opinions where auditor_id = '<ID>')     as avis_audit,
       (select count(*) from metric_reviews where auditor_id = '<ID>')     as revues,
       (select count(*) from project_assignments where researcher_id = '<ID>') as affectations,
       (select count(*) from projects where institution_id = '<ID>')       as projets,
       (select count(*) from scoring_configs where owner_user_id = '<ID>') as configurations;"
```

- Tous les compteurs à 0 : **suppression** (4.2).
- Sinon : **anonymisation** (4.3). Les pièces restent, mais plus rien ne relie le compte à la
  personne. L'art. 17.3 permet de conserver ce qui est nécessaire à une obligation légale ou à la
  constatation de droits ; le préciser dans la réponse au demandeur.

### 4.2 Suppression

Supprimer d'abord les fichiers. Les chemins affichés sont relatifs au volume `storage`, monté sur
`/code/storage` dans le conteneur `api` :

```bash
$PSQL -At -c "select avatar_path from users where id = '<ID>' and avatar_path is not null
              union all
              select mandate_letter_path from companies where owner_user_id = '<ID>' and mandate_letter_path is not null;"
# pour chaque chemin affiché :
docker compose $PROD exec api rm -f "/code/storage/<chemin>"
```

Puis la base, dans une transaction :

```bash
$PSQL <<'SQL'
begin;
-- Copies du nom dans les notifications reçues par les Administrateurs (demande d'accès,
-- inscription) : elles appartiennent aux Administrateurs et ne partent pas avec le compte.
delete from notifications
 where message ilike '%' || (select name from users where id = '<ID>') || '%';
-- Demande d'inscription d'entreprise jamais validée : retirer la lettre de mandat et les échanges.
update companies
   set mandate_letter_path = null, info_request_message = null, info_response_message = null
 where owner_user_id = '<ID>';
-- Le reste suit par ON DELETE CASCADE (jetons, demandes d'accès, notifications du compte,
-- portefeuilles, rattachements) ou SET NULL (journal d'audit, entreprise, rapports audités).
delete from users where id = '<ID>';
commit;
SQL
```

Avant le `commit`, vérifier que la suppression de notifications ne touche que les bonnes lignes. Si
le nom est vide ou trop court (par exemple deux lettres), remplacer ce filtre par une sélection
manuelle des `id`.

### 4.3 Anonymisation

```bash
$PSQL <<'SQL'
begin;
delete from notifications
 where message ilike '%' || (select name from users where id = '<ID>') || '%';
update users
   set email = 'supprime-' || id || '@invalid.local',
       name = null,
       avatar_path = null,
       password_hash = null,
       active = false
 where id = '<ID>';
delete from email_change_requests where user_id = '<ID>';
delete from password_reset_tokens where user_id = '<ID>';
delete from account_activation_tokens where user_id = '<ID>';
commit;
SQL
```

Supprimer aussi la photo de profil du volume `storage`, comme en 4.2.

## 5. Sauvegardes

Les sauvegardes quotidiennes (`docs/DEPLOIEMENT_ORACLE.md`, section 7) contiennent encore les
données effacées jusqu'à leur rotation, au bout de 14 jours. Ne pas les restaurer sans réappliquer
les effacements faits depuis leur date. Pour cela, tenir le registre de la section 6.

## 6. Registre

Pour chaque demande, noter dans le registre de l'exploitant :
- la date de réception et la date de réponse ;
- le droit exercé ;
- l'`<ID>` du compte ;
- la suite donnée : export, suppression ou anonymisation, avec son motif.

Ne pas y recopier les données de la personne.
