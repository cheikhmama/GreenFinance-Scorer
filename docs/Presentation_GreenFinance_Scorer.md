---
marp: true
theme: default
paginate: true
size: 16:9
title: GreenFinance-Scorer — Présentation du projet
description: Présentation de cadrage — état d'avancement, preuves et prochaines étapes
style: |
  :root {
    --green: #0f6b4f;
    --green-light: #e8f4ef;
    --blue: #16324f;
    --grey: #5b6573;
  }
  section {
    color: var(--blue);
    font-family: Aptos, "Segoe UI", Arial, sans-serif;
    padding: 52px 64px;
  }
  h1 { color: var(--green); font-size: 1.7em; }
  h2 { color: var(--blue); }
  strong { color: var(--green); }
  blockquote {
    border-left: 6px solid var(--green);
    background: var(--green-light);
    padding: 10px 20px;
  }
  table { font-size: 0.72em; }
  small { color: var(--grey); }
---

<!-- _class: lead -->

# Comment transformer des rapports ESG en décisions d'investissement traçables ?

## GreenFinance-Scorer

Plateforme à vocation **open source** pour :

- évaluer un portefeuille avec des pondérations ESG configurables ;
- calculer l'empreinte carbone Scope 1, 2 et 3 ;
- expliquer chaque résultat à partir de preuves documentaires.

<small>[Votre nom] · [Cadre de présentation] · [Date]</small>

<!--
RÉPONSE ORALE EXACTE — 35 s
« GreenFinance-Scorer vise à transformer des rapports ESG et climat difficiles à exploiter en résultats comparables, configurables et traçables pour l'investissement. Le socle technique et le modèle de données sont en place ; le pipeline documentaire est en validation. Les moteurs de scoring ESG, de calcul PCAF et d'explicabilité constituent les prochaines briques métier à construire. »

VISUEL SUGGÉRÉ
Une ligne simple : Rapport PDF → Données sourcées → Score et carbone → Décision portefeuille.
-->

---

# Quel problème concret la plateforme résout-elle ?

### Des informations essentielles, mais difficiles à exploiter

- Les données ESG et carbone sont dispersées dans des rapports longs et hétérogènes.
- Les périmètres, années, unités et méthodes ne sont pas toujours directement comparables.
- L'extraction manuelle est lente et difficile à reproduire à l'échelle d'un portefeuille.
- Un chiffre sans page source ni méthode est difficile à vérifier et à auditer.

> **Besoin central :** passer d'un PDF complexe à une donnée comparable sans perdre sa provenance.

<!--
RÉPONSE ORALE EXACTE — 55 s
« Le problème n'est pas l'absence totale de données ESG : elles existent, mais elles sont enfermées dans des rapports parfois très longs, présentées avec des formats, unités et périmètres différents. Pour un investisseur ou un auditeur, les extraire et les comparer manuellement prend du temps et rend la décision difficile à reproduire. La plateforme cherche donc à automatiser cette chaîne tout en conservant la page et le document qui justifient chaque valeur. »

VISUEL SUGGÉRÉ
À gauche, plusieurs couvertures PDF ; au centre, une loupe ; à droite, une donnée avec son numéro de page.
-->

---

# Quel résultat final le projet veut-il produire ?

## Une chaîne complète, reproductible et vérifiable

```text
Rapports annuels / ESG / climat
                ↓
Structuration et recherche des pages pertinentes
                ↓
Données ESG et carbone + preuve documentaire
                ↓
Scores E, S, G configurables + empreinte carbone financée
                ↓
Vue portefeuille + explication du résultat
```

**Principe directeur :** aucune valeur finale ne doit être dissociée de sa source, de sa méthode et de sa configuration de calcul.

<!--
RÉPONSE ORALE EXACTE — 50 s
« L'objectif est de construire un flux de bout en bout. Un rapport est d'abord structuré ; seules les pages pertinentes sont recherchées ; les données sont ensuite extraites avec leurs preuves. Elles alimentent un score ESG configurable et un calcul carbone, puis les résultats sont agrégés au niveau du portefeuille. La valeur différenciante recherchée est la traçabilité : une décision doit pouvoir être reliée à la donnée, à la formule et au passage documentaire qui la justifie. »

VISUEL SUGGÉRÉ
Utiliser le flux central comme schéma principal et révéler les blocs progressivement.
-->

---

# À qui la plateforme apporte-t-elle de la valeur ?

| Utilisateurs prioritaires | Besoin principal |
|---|---|
| **Investisseur** | Comparer des entreprises et mesurer un portefeuille selon sa propre pondération |
| **Entreprise** | Déposer ses rapports et suivre les données qui en sont extraites |
| **Auditeur** | Contrôler les indicateurs, leurs méthodes et leurs preuves documentaires |

### Rôles complémentaires déjà prévus dans l'architecture

Administrateur · Chercheur · Institution

<small>Le récit de la présentation se concentre sur les trois utilisateurs qui portent le parcours métier principal.</small>

<!--
RÉPONSE ORALE EXACTE — 45 s
« Le modèle prévoit six rôles, mais trois structurent le parcours principal. L'entreprise fournit le rapport, l'auditeur contrôle les données et leurs preuves, et l'investisseur utilise les résultats pour analyser son portefeuille. Les rôles administrateur, chercheur et institution sont prévus dans l'architecture, mais les présenter au même niveau diluerait le message principal. »

VISUEL SUGGÉRÉ
Triangle Entreprise–Auditeur–Investisseur, avec les trois rôles secondaires en périphérie.
-->

---

# Comment passe-t-on du PDF à une décision d'investissement ?

| Maillon du parcours | État réel |
|---|---|
| Dépôt, cycle de vie et modèle de données | **Socle réalisé** |
| Structuration des PDF avec Docling | **Pilote exécuté ; persistance en validation** |
| Recherche sémantique bge-m3 / FAISS | **Code préparatoire ; test 4.3 non validé** |
| Extraction contrôlée et preuve de page | **À valider aux sous-étapes suivantes** |
| Scoring ESG et calcul PCAF | **Planifiés ; moteurs non implémentés** |
| Agrégation portefeuille et explicabilité | **Planifiées** |

> La présentation distingue volontairement **réalisé**, **en validation** et **planifié**.

<!--
RÉPONSE ORALE EXACTE — 65 s
« Le parcours cible va du dépôt du rapport jusqu'à la décision portefeuille. Aujourd'hui, le socle applicatif et le schéma de données sont réalisés, et la structuration documentaire a déjà fait l'objet d'un premier pilote. La recherche sémantique est préparée mais pas encore validée selon le protocole attendu. Enfin, les moteurs ESG, PCAF, portefeuille et explicabilité restent planifiés. Cette distinction évite de confondre une architecture prête à recevoir la logique métier avec un produit métier déjà terminé. »

VISUEL SUGGÉRÉ
Une barre de progression à six blocs avec le même code couleur que le tableau.
-->

---

# Pourquoi cette architecture technique ?

```text
Utilisateurs et futures interfaces
                ↓
        API FastAPI versionnée
                ↓
 ┌──────────┬─────────┬────────┬────────────────┬─────────────┐
 │ Ingestion│ Scoring │ Carbone│ Explicabilité  │ Portefeuille│
 └──────────┴─────────┴────────┴────────────────┴─────────────┘
                ↓
 PostgreSQL + pgvector · Redis · stockage documentaire
```

- **SQLModel/PostgreSQL** : intégrité et traçabilité des données métier.
- **FAISS local** : validation volontairement découplée de la recherche sémantique au stade pilote.
- **pgvector** : intégration sémantique future dans la plateforme.
- **Docker** : environnement reproductible et composants isolés.

<!--
RÉPONSE ORALE EXACTE — 60 s
« L'architecture est modulaire : l'API FastAPI expose des domaines séparés pour l'ingestion, le scoring, le carbone, l'explicabilité et le portefeuille. SQLModel et PostgreSQL assurent la cohérence du schéma ; Redis et Docker préparent une exécution reproductible et des traitements découplés. Pour le pilote, FAISS reste local et en mémoire afin de mesurer la qualité de la recherche sans dépendre de pgvector ; l'intégration en base viendra après validation expérimentale. »

VISUEL SUGGÉRÉ
Conserver ce diagramme boîtes/flèches ; ne pas montrer l'arborescence complète de app/ sur la slide principale.
-->

---

# Comment le score ESG évitera-t-il l'effet « boîte noire » ?

## Méthode cible — encore à arbitrer et à valider

```text
Indicateurs sourcés
      ↓
Normalisation documentée
      ↓
Pondérations configurables et versionnées
      ↓
Scores Environnement · Social · Gouvernance
      ↓
Score global et décomposition explicative
```

Les choix à formaliser portent notamment sur les unités, les données manquantes, la matérialité sectorielle, les bornes de normalisation et les règles d'agrégation.

> Le schéma peut déjà stocker configurations et scores ; **la formule n'est pas encore implémentée ni validée**.

<!--
RÉPONSE ORALE EXACTE — 60 s
« Le score ESG doit rester explicable. La cible consiste à normaliser des indicateurs sourcés, à leur appliquer des pondérations configurables et versionnées, puis à produire les scores E, S, G et global avec leur décomposition. Le modèle de données peut déjà enregistrer plusieurs scores pour un même rapport selon plusieurs configurations. En revanche, la formule exacte, le traitement des valeurs manquantes et la matérialité sectorielle restent à concevoir et à valider ; je ne présente donc pas encore d'exemple numérique comme un résultat acquis. »

VISUEL SUGGÉRÉ
Entonnoir ou chaîne en cinq étapes ; ajouter un badge « cible, non encore opérationnelle ».
-->

---

# Comment l'empreinte carbone et les émissions financées seront-elles calculées ?

### Ce que le modèle de données prévoit déjà

- émissions **Scope 1, Scope 2 et Scope 3** en tCO₂e ;
- année, méthode — rapportée, estimée ou calculée — et catégorie GES ;
- preuve documentaire ;
- score de qualité PCAF borné de 1 à 5.

### Chaîne de calcul cible

```text
Émissions de l'entreprise
        × facteur d'attribution adapté à la classe d'actif
        = émissions financées
        → agrégation au niveau du portefeuille
```

> Le schéma est prêt ; les facteurs d'émission, règles d'unités et formules PCAF restent à implémenter et tester.

<!--
RÉPONSE ORALE EXACTE — 65 s
« La plateforme doit d'abord conserver les émissions Scope 1, 2 et 3 de l'entreprise avec leur année, leur méthode et leur preuve. Pour l'investisseur, la cible est ensuite d'appliquer le facteur d'attribution approprié à la classe d'actif afin d'obtenir les émissions financées, puis de les agréger au niveau du portefeuille. Le schéma stocke déjà les champs nécessaires, notamment un score de qualité PCAF de 1 à 5. Cela ne signifie pas encore que la plateforme est conforme PCAF : le moteur, les facteurs, les contrôles d'unités et les cas par classe d'actif restent à développer. »

VISUEL SUGGÉRÉ
Deux niveaux : empreinte de l'entreprise en haut, part financée et portefeuille en bas.
-->

---

# Qu'est-ce qui démontre aujourd'hui la faisabilité documentaire ?

## Premier passage Docling — pilote de quatre entreprises

| Entreprise | Pages | Tableaux détectés | Concordance pages |
|---|---:|---:|---:|
| Schneider Electric | 290 | 174 | Oui |
| Microsoft | 25 | 28 | Oui |
| Ørsted | 218 | 166 | Oui |
| Ingka Group | 100 | 73 | Oui |
| **Total** | **633** | **441** | **4/4** |

**Démonstration recommandée :** Microsoft d'abord, de la structuration du rapport jusqu'à la page source attendue.

<small>Ces résultats prouvent la structuration des documents, pas encore la qualité finale de la recherche ni de l'extraction.</small>

<!--
RÉPONSE ORALE EXACTE — 65 s
« Un premier passage Docling a traité quatre rapports vérifiés, soit 633 pages et 441 tableaux détectés. Pour chacun, le nombre de pages obtenu correspond au PDF source et aucune erreur n'est enregistrée dans le résultat de cette sous-étape. C'est une preuve de faisabilité de la structuration, pas encore une preuve de qualité de bout en bout. La démonstration la plus crédible consiste donc à commencer par Microsoft, le rapport le plus court, puis à vérifier que la recherche retrouve effectivement la page attendue. »

VISUEL SUGGÉRÉ
Le tableau ci-dessus, accompagné d'une capture du rapport Microsoft et d'un encadré autour de la page attendue.
-->

---

# Où en est exactement le projet ?

## État d'avancement honnête

1. **Étapes 1 à 3 sur 21 : documentées et validées**  
   environnement, architecture modulaire, schéma pivot et migrations.

2. **Étape 4 : expérimentation locale en cours**  
   structuration documentaire réalisée une première fois ; persistance durable et validation sémantique à finaliser.

3. **Étapes suivantes : logique métier à construire**  
   ingestion intégrée, authentification et espaces utilisateurs, scoring ESG, carbone/PCAF, explicabilité et portefeuille.

> GreenFinance-Scorer est aujourd'hui un **socle crédible avec un pilote documentaire**, pas encore un MVP métier complet.

<!--
RÉPONSE ORALE EXACTE — 60 s
« Le projet suit un plan de 21 étapes. Les trois premières ont posé et validé l'environnement, l'architecture et le schéma pivot. L'étape 4 mène actuellement le pilote documentaire : une première structuration a réussi, mais les artefacts doivent être persistés et la recherche sémantique doit encore satisfaire son protocole de validation. Les moteurs de scoring, de carbone, d'explicabilité et d'agrégation portefeuille viennent plus tard. Le bon diagnostic est donc : trajectoire cohérente, mais produit métier encore incomplet. »

VISUEL SUGGÉRÉ
Roadmap en trois bandes : Validé / En validation / Planifié. Éviter 21 petites cases illisibles.
-->

---

# Quelle valeur est déjà prouvée — et laquelle reste à mesurer ?

| Déjà démontré | Bénéfices métier attendus |
|---|---|
| Architecture modulaire et API versionnée | Réduction du temps d'analyse |
| Schéma pivot de **15 tables et 9 énumérations** | Comparaison cohérente des entreprises |
| Migration réversible sur base fraîche | Analyse personnalisée par pondération |
| Baseline documentée : **71/71 tests, 98 % de couverture**¹ | Décisions plus transparentes et auditables |
| Pilote documentaire : **4 rapports, 633 pages** | Mesure carbone consolidée du portefeuille |

<small>¹ Résultat consigné à la fin de l'Étape 3, le 12 août 2026 ; ce n'est pas une mesure métier ni un ROI utilisateur.</small>

<!--
RÉPONSE ORALE EXACTE — 55 s
« La valeur déjà démontrée est d'abord technique : une architecture modulaire, un schéma pivot de quinze tables, des migrations réversibles et une baseline de tests documentée à la fin de l'étape 3. Le pilote documentaire apporte ensuite une première preuve sur quatre rapports. Les bénéfices métier — gain de temps, comparabilité, personnalisation et auditabilité — restent des bénéfices attendus : ils devront être mesurés sur des parcours utilisateurs et un corpus élargi avant d'être présentés comme un ROI établi. »

VISUEL SUGGÉRÉ
Séparer nettement « preuves actuelles » et « valeur à mesurer » pour éviter toute surpromesse.
-->

---

# Quel défi a produit l'apprentissage le plus important ?

## Les traitements coûteux doivent être persistants et reprenables

- Le premier passage des quatre rapports a duré environ **2 h 59** sur CPU.
- Seules les statistiques avaient été conservées, pas les documents Docling structurés.
- Toute itération sur la recherche imposait donc une reconversion inutile.

### Réponse d'architecture retenue

1. convertir une fois et sauvegarder un artefact structuré par rapport ;
2. valider son intégrité avant de le considérer comme réutilisable ;
3. séparer conversion, indexation et évaluation ;
4. tester Microsoft de bout en bout avant le lot complet.

<!--
RÉPONSE ORALE EXACTE — 60 s
« Le principal apprentissage est qu'un résultat intermédiaire coûteux doit être traité comme un véritable artefact. Le premier passage des quatre rapports a pris près de trois heures, mais seuls les résultats statistiques ont été sauvegardés. Il fallait donc reconvertir pour tester la recherche. La correction consiste à séparer la conversion, l'indexation et l'évaluation, à sauvegarder chaque document structuré de manière vérifiable, puis à commencer par Microsoft afin de détecter rapidement les erreurs méthodologiques avant de relancer tout le corpus. »

VISUEL SUGGÉRÉ
Avant : PDF → 3 h → statistiques seulement. Après : PDF → JSON durable → itérations rapides.
-->

---

<!-- _class: lead -->

# Quelle est la prochaine preuve décisive ?

1. **Valider Microsoft de bout en bout**  
   persistance Docling → recherche de pages → extraction → comparaison à la vérité terrain.

2. **Corriger et mesurer le Prompt 4.3**  
   deux requêtes fixes, huit pages uniques, rang exact de la page attendue, absences comptées comme échecs.

3. **Étendre prudemment la validation**  
   quatre rapports vérifiés, puis huit entreprises vérifiées avant d'appliquer le critère officiel 6/8.

4. **Industrialiser après la preuve**  
   intégrer le pipeline à l'application, puis construire scoring ESG, PCAF, portefeuille et explicabilité.

> **Conclusion :** la direction est bonne ; la priorité est maintenant de transformer le prototype documentaire en preuve reproductible.

<small>[Remerciements / encadrant(s), si applicable] · Questions ?</small>

<!--
RÉPONSE ORALE EXACTE — 65 s
« La prochaine preuve décisive n'est pas une nouvelle fonctionnalité : c'est un parcours Microsoft entièrement reproductible, du PDF jusqu'à la valeur comparée à la vérité terrain. Ensuite, la recherche doit être corrigée pour classer huit pages uniques et consigner le rang exact de la bonne page. Le test sera étendu aux quatre rapports vérifiés, puis à huit entreprises réellement vérifiées avant d'appliquer le seuil officiel de six sur huit. Ce n'est qu'après cette preuve que l'intégration et les moteurs métier pourront être industrialisés sur une base fiable. »

VISUEL SUGGÉRÉ
Quatre jalons numérotés. Terminer sur la phrase de conclusion, sans ajouter une nouvelle promesse.

SOURCES FACTUELLES INTERNES
- docs/GreenFinance-Scorer_Etape1_Rapport-Technique.pdf
- docs/GreenFinance-Scorer_Etape2_Rapport-Technique.pdf
- docs/GreenFinance-Scorer_Etape3_Rapport-Technique.pdf
- data_test/prompt_4_2_structuration.json
- data_test/ground_truth.yaml
- notebooks/_prompt_4_3_indexation.py

HYPOTHÈSES DE FORMAT À CONFIRMER
- Durée : 15 à 20 minutes, puis questions.
- Audience : jury mixte, métier et technique.
- Style : sobre, corporate, vert/bleu.
- Démonstration : captures ou séquence enregistrée, pas de dépendance à un parcours live complet.
- Remplacer les champs [Votre nom], [Cadre de présentation], [Date] et les remerciements.
-->
