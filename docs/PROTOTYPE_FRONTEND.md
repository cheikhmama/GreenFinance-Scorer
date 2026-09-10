# Prototype frontend multi-acteurs

## Objectif

Le prototype permet d'évaluer l'UI/UX des six espaces avant l'intégration des API métier. Il est isolé de
l'authentification réelle, utilise uniquement des données de démonstration et ne modifie pas les protections
`RequireRole` des routes `/admin`, `/company`, `/audit`, `/investor`, `/researcher` et `/institution`.

En développement, le point d'entrée est :

```text
http://localhost:5173/prototype
```

Dans un build de démonstration, il faut définir :

```text
VITE_ENABLE_PROTOTYPE=true
```

Sans cette variable, les routes du prototype ne sont pas montées en production.

## Espaces disponibles

| Espace | Pages principales |
|---|---|
| Administrateur | Tableau de bord, Utilisateurs, Entreprises, Rapports, Méthodologie ESG |
| Entreprise | Tableau de bord, Rapports, Résultats ESG, Profil |
| Auditeur | Tableau de bord, Dossiers affectés, Historique |
| Investisseur | Tableau de bord, Entreprises, Comparaison, Portefeuilles |
| Chercheur | Tableau de bord, Données, Analyses, Rattachements |
| Institution | Tableau de bord, Entreprises, Chercheurs, Analyses |

Le sélecteur « Voir comme » de la barre supérieure est exclusivement un outil d'évaluation. Il ne représente
pas une capacité d'usurpation de rôle dans l'application réelle.

## Scénarios de recette UX

### Création d'un acteur

```text
Administrateur → Utilisateurs → Ajouter un utilisateur
→ sélectionner le rôle → afficher automatiquement le formulaire correspondant
→ renseigner les informations métier → Créer et inviter
→ Prévisualiser l'espace du nouveau compte
```

Pour le rôle `Entreprise`, le parcours simule l'analyse du site officiel. Les domaines Microsoft, Ørsted,
Apple, SNIM et Ingka Group remplissent le logo, le secteur et le pays à partir d'un catalogue local vérifié.
Plusieurs emplacements d'icône sont essayés successivement afin qu'une ressource absente ne bloque pas la
vignette ; les autres domaines laissent les champs métier à confirmer manuellement. L'administrateur choisit
ensuite une URL officielle de rapport ou un PDF local. La création ajoute de manière cohérente le compte invité,
l'entreprise non publiée et le document soumis à l'état partagé. Aucun site n'est réellement exploré et aucun
fichier n'est transmis à un serveur.

Le formulaire de création ne permet pas de créer un autre Administrateur. Il propose uniquement, dans cet
ordre : Entreprise, Investisseur, Auditeur, Institution et Chercheur. Après le choix, l'icône du rôle et son
formulaire spécialisé apparaissent. Le logo d'une entreprise est présenté dans une zone visuelle dédiée ; son
URL technique n'est jamais demandée à l'administrateur. Aucun cadre de logo n'est visible avant le chargement
réussi de l'image. La vignette apparaît ensuite sans label, dans une colonne compacte alignée avec les champs
Secteur et Pays.

### Cycle d'un rapport

```text
Entreprise → soumettre un rapport
→ Administrateur → affecter un auditeur
→ Auditeur → contrôler et soumettre un avis
→ Administrateur → demander une correction
→ Entreprise → envoyer la correction
→ Administrateur → valider et publier
```

### Décision d'investissement

```text
Investisseur → Entreprises → ouvrir une preuve
→ Comparaison → comparer Microsoft et Ørsted
→ ajouter une position → Portefeuilles
```

### Collaboration scientifique

```text
Institution → Chercheurs → inviter
→ Chercheur → Rattachements → accepter
→ Chercheur → Analyses → créer une analyse institutionnelle
→ Institution → Analyses → consulter ou exporter
```

## Règles du prototype

- Les changements sont conservés pendant la navigation, mais disparaissent au rechargement de la page.
- « Réinitialiser la démonstration » restaure les fixtures initiales.
- Une action principale produit toujours un changement d'état, une navigation, une modale ou une confirmation.
- Les valeurs ESG affichent la période, l'unité, la qualité et une preuve documentaire simulée.
- Aucun fichier JSON Docling volumineux n'est chargé dans le navigateur.
- Aucun appel aux services backend métier n'est effectué.

## Limite assumée

Le prototype valide la structure des pages et les parcours. Les autorisations serveur, les transactions, la
persistance PostgreSQL, l'extraction documentaire et les calculs réels ne deviennent opérationnels qu'après
connexion aux contrats API correspondants.
