# GreenFinance Scorer — script oral de soutenance

Durée cible : **environ 24 min 40**, démonstration comprise.

> Remplacer les champs personnels de la couverture et insérer `demo_greenfinance.mp4` sur la slide 12.

## 01 — GreenFinance Scorer (0:45)

Durée cible : 45 secondes.

        GreenFinance Scorer vise à transformer des rapports ESG et climat difficiles à exploiter en données comparables, configurables et surtout traçables. La question centrale de ce projet est simple : peut-on faire confiance à un score si l’on ne peut pas revenir au document qui le justifie ?

        Transition : Pour comprendre la solution, il faut d’abord comprendre pourquoi la donnée ESG reste difficile à utiliser.

## 02 — La donnée ESG reste enfermée (1:15)

Durée cible : 1 minute 15.

        Les données ESG existent déjà, mais elles sont enfermées dans des rapports longs et hétérogènes. Une même notion peut être présentée dans un tableau, une note méthodologique ou une annexe, avec des unités et des périodes différentes. L’extraction manuelle est lente et difficile à reproduire à l’échelle d’un portefeuille. Le problème n’est donc pas seulement de trouver un chiffre, mais de préserver son contexte et sa provenance.

        Transition : À cette complexité documentaire s’ajoute une seconde difficulté : la divergence des méthodes de notation.

## 03 — Des scores divergents (1:30)

Durée cible : 1 minute 30.

        Le problème ne se limite pas à l’accès aux rapports. Les notations ESG elles-mêmes divergent fortement. Une étude académique comparant six fournisseurs observe des corrélations comprises entre 38 et 71 %. La différence vient notamment du périmètre retenu, de la manière de mesurer les indicateurs et des pondérations. Pour l’utilisateur, un score sans méthode ni preuve devient une boîte noire difficile à auditer.

        Transition : GreenFinance Scorer cherche précisément à remplacer cette boîte noire par une chaîne de preuves.

## 04 — Chaque résultat revient à sa source (1:30)

Durée cible : 1 minute 30.

        La plateforme cible un flux simple : analyser, extraire, vérifier, calculer et expliquer. La différence essentielle est que la donnée ne se limite pas à un nombre. Elle conserve la valeur originale, l’unité, la période, le périmètre, le document et la page. Si une information n’est pas clairement présente, le système doit s’abstenir et demander une vérification.

        Transition : Cette chaîne répond à quatre objectifs complémentaires.

## 05 — L’innovation est la chaîne de confiance (1:20)

Durée cible : 1 minute 20.

        Le projet ne cherche pas à ajouter une note ESG supplémentaire. L’innovation réside dans l’intégration d’une chaîne complète : extraction sourcée, scoring configurable, calcul carbone et décision portefeuille explicable. L’objectif scientifique est de rendre visibles les hypothèses, les pondérations et les preuves qui produisent le résultat.

        Transition : Cette chaîne réunit six acteurs autour de la même donnée de référence.

## 06 — Six acteurs (1:30)

Durée cible : 1 minute 30.

        Six rôles sont prévus. L’administrateur crée et gère les comptes. L’entreprise dépose son rapport. L’auditeur vérifie les indicateurs et les preuves. L’investisseur compare et décide. Le chercheur analyse les données autorisées, tandis que l’institution organise la collaboration scientifique. Chaque rôle possède un espace privé, mais tous partagent la même donnée validée.

        Transition : Le workflow principal relie l’entreprise, le système, l’administrateur et l’auditeur.

## 07 — Du dépôt à la publication (1:50)

Durée cible : 1 minute 50.

        Le workflow commence par le dépôt du rapport. Le système lance l’analyse documentaire. L’administrateur affecte ensuite un auditeur, qui vérifie les indicateurs, l’unité, la période et la preuve. Si une information manque, une correction est demandée à l’entreprise. La nouvelle version revient dans le circuit avant validation et publication. Le prototype simule tout ce parcours ; le backend réel couvre déjà une partie Entreprise–Administrateur–Auditeur, mais l’intégration complète reste à terminer.

        Transition : Une fois validées, ces données alimentent plusieurs usages sans créer de copies contradictoires.

## 08 — Trois usages décisionnels (1:30)

Durée cible : 1 minute 30.

        Le frontend propose six espaces, mais cette slide montre trois usages majeurs. L’entreprise suit les résultats et ouvre la preuve de chaque valeur. L’investisseur compare des entreprises selon des données homogènes et sourcées. Le chercheur et l’institution construisent et partagent des analyses. Les captures proviennent du prototype réel ; les données sont simulées et aucun appel métier backend n’est effectué à ce stade.

        Transition : La valeur de ces interfaces dépend entièrement de la fiabilité du pipeline documentaire.

## 09 — Chaîne de fiabilité (2:15)

Durée cible : 2 minutes 15.

        La fiabilité vient d’une succession de contrôles, pas d’un seul appel à un modèle. Le PDF original est conservé. Docling et l’OCR structurent les pages et tableaux. Le rapport est indexé par bge-m3 et FAISS afin de retrouver les passages candidats. L’extraction doit ensuite produire un JSON contraint, puis les valeurs sont comparées aux pages et à la vérité terrain. Les étapes 4.2 et 4.3 ont été exécutées ; 4.4 à 4.6 restent à finaliser. Une valeur incertaine doit être signalée, jamais inventée.

        Transition : Ce pipeline s’intègre dans une architecture qui sépare clairement les responsabilités.

## 10 — Architecture modulaire (1:45)

Durée cible : 1 minute 45.

        L’architecture sépare quatre niveaux. Le frontend React fournit les espaces par rôle. L’API FastAPI expose les fonctions versionnées et applique validation et permissions. Les modules métier isolent les responsabilités. PostgreSQL conserve les données structurées, Redis prépare les traitements asynchrones et le stockage conserve les documents. Le pipeline IA reste un composant remplaçable : Claude, Gemini ou un modèle local peuvent respecter le même schéma de sortie.

        Transition : Chaque technologie a donc été choisie pour une propriété précise du système.

## 11 — Technologies (1:30)

Durée cible : 1 minute 30.

        React et TypeScript structurent les interfaces multi-rôles. FastAPI et Pydantic rendent les contrats d’API explicites. PostgreSQL et SQLModel garantissent l’intégrité et le versionnement. Docling et PaddleOCR comprennent les PDF et les tableaux. bge-m3 et FAISS permettent de mesurer la recherche sémantique indépendamment du modèle génératif. Docker et la CI rendent l’environnement reproductible. Le choix technologique répond donc directement à un besoin de confiance.

        Transition : Ces briques deviennent concrètes dans le parcours de démonstration.

## 12 — Démonstration (3:30)

Durée cible : 3 minutes 30.

        Annoncer clairement qu’il s’agit d’un prototype interactif utilisant des données simulées. La vidéo doit montrer un seul fil narratif : l’administrateur crée une entreprise, le rapport est déposé, l’auditeur ouvre les preuves, l’administrateur publie puis l’investisseur compare les résultats. Terminer par un aperçu des espaces Recherche et Institution. Conserver les captures d’écran comme solution de secours si la vidéo ne démarre pas.

        Transition : Le prototype valide les parcours ; le pipeline expérimental fournit les premières preuves techniques.

## 13 — Résultats actuels (2:00)

Durée cible : 2 minutes.

        Le corpus actif contient Microsoft, Ørsted et Ingka Group : 343 pages et 267 tableaux structurés avec concordance du nombre de pages. Le benchmark de recherche retrouve 11 indicateurs sur 15 dans les huit meilleures pages, soit 73,3 %. Ørsted et Ingka atteignent 100 % sur ce test ; Microsoft échoue au top 8 parce que la page correcte arrive au rang 10. Il faut insister : ce résultat mesure la récupération documentaire, pas encore l’exactitude des valeurs. Les étapes 4.4 à 4.6 n’ont pas encore produit de verdict.

        Transition : Ces résultats démontrent la faisabilité tout en révélant clairement les limites à traiter.

## 14 — Limites et prochaines preuves (1:45)

Durée cible : 1 minute 45.

        Les limites sont assumées. Le prototype frontend n’utilise pas encore les API métier. Le corpus ne couvre que trois entreprises. Les étapes 4.4 à 4.6 restent à finaliser. Le traitement CPU est encore long et les moteurs de scoring et de PCAF sont des cibles. La trajectoire est néanmoins mesurable : connecter les API, élargir le corpus, rendre le pipeline asynchrone et atteindre au minimum 90 % de valeurs correctes, 85 % de pages exactes et zéro hallucination avant le GO.

        Transition : La valeur finale n’est donc pas seulement l’automatisation, mais une automatisation contrôlée.

## 15 — Conclusion (0:45)

Durée cible : 45 secondes.

        GreenFinance Scorer part d’un problème concret : des données ESG dispersées et des scores difficiles à auditer. La solution proposée relie chaque résultat à sa source, rend les pondérations configurables et prépare l’analyse carbone et portefeuille. Le projet démontre déjà un prototype multi-acteurs et un pilote documentaire jusqu’à la recherche sémantique. La prochaine étape décisive est de valider l’extraction avec les seuils annoncés. Un score devient digne de confiance lorsqu’il peut être expliqué, reproduit et audité.

        Merci. Je suis prêt à répondre à vos questions.
