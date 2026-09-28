# GreenFinance Scorer — script oral de soutenance

Durée cible : **environ 23 min 40**, démonstration comprise.

> Remplacer les champs personnels de la couverture et insérer `demo_greenfinance.mp4` sur la slide 12.

## 01 — Page de garde (0:40)

Durée cible : 40 secondes.

        Bonjour. Je vais vous présenter GreenFinance Scorer, une plateforme open source d’évaluation ESG et climatique des portefeuilles d’investissement. Elle couvre l’analyse des rapports, le scoring configurable, les émissions Scope 1, 2 et 3, l’empreinte financée et la traçabilité documentaire.

        Transition : La présentation est organisée en six parties.

## 02 — Sommaire (0:45)

Durée cible : 45 secondes.

        La soutenance commence par le contexte, la problématique, la solution et les objectifs. Elle présente ensuite les acteurs et le workflow, puis le pipeline documentaire, l’architecture et les choix technologiques. Une démonstration illustre le parcours complet. Enfin, les résultats, les recommandations, les perspectives et la conclusion sont présentés.

        Transition : Commençons par le contexte et le besoin à l’origine du projet.

## 03 — Contexte et problématique (1:40)

Durée cible : 1 minute 30.

        Les données ESG sont publiées dans des rapports dont la longueur peut aller de quelques pages à plusieurs centaines de pages. Les formats, unités, années et périmètres varient fortement. À cette difficulté documentaire s’ajoutent des méthodes propriétaires, des pondérations imposées et une provenance parfois difficile à vérifier. Le besoin est donc double : automatiser l’analyse et rendre chaque résultat auditable.

        Transition : La solution proposée répond directement à ces deux dimensions.

## 04 — Solution proposée (1:30)

Durée cible : 1 minute 30.

        La plateforme applique cinq opérations : analyser, extraire, vérifier, calculer et expliquer. Chaque donnée conserve sa valeur originale, son unité, sa période, son périmètre, le document et la page correspondante. Si une information n’est pas clairement présente, le système la signale pour vérification au lieu de produire une valeur non justifiée.

        Transition : Cette chaîne répond à quatre objectifs complémentaires.

## 05 — Objectifs et valeur ajoutée (1:20)

Durée cible : 1 minute 20.

        Le projet intègre dans une même plateforme l’extraction sourcée, le scoring configurable, le calcul carbone et l’analyse de portefeuille. Les hypothèses, les pondérations et les preuves restent visibles afin que les résultats puissent être vérifiés et reproduits.

        Transition : Cette chaîne réunit six acteurs autour de la même donnée de référence.

## 06 — Acteurs et responsabilités (1:30)

Durée cible : 1 minute 30.

        Six rôles sont prévus. L’administrateur crée et gère les comptes. L’entreprise dépose son rapport. L’auditeur vérifie les indicateurs et les preuves. L’investisseur compare et décide. Le chercheur analyse les données autorisées, tandis que l’institution organise la collaboration scientifique. Chaque rôle possède un espace privé, mais tous partagent la même donnée validée.

        Transition : Le workflow principal relie l’entreprise, le système, l’administrateur et l’auditeur.

## 07 — Workflow principal (1:50)

Durée cible : 1 minute 50.

        Le workflow commence par le dépôt du rapport. Le système lance l’analyse documentaire. L’administrateur affecte ensuite un auditeur, qui vérifie les indicateurs, l’unité, la période et la preuve. Si une information manque, une correction est demandée à l’entreprise. La nouvelle version revient dans le circuit avant validation et publication. Les changements de statut et les notifications sont synchronisés entre les espaces concernés.

        Transition : Une fois validées, ces données alimentent plusieurs usages sans créer de copies contradictoires.

## 08 — Fonctionnalités principales (1:30)

Durée cible : 1 minute 30.

        La plateforme propose six espaces. Cette diapositive illustre trois usages majeurs : l’entreprise consulte ses résultats et les preuves, l’investisseur compare les entreprises et analyse son portefeuille, tandis que le chercheur et l’institution construisent, partagent et exportent leurs analyses.

        Transition : La valeur de ces interfaces dépend entièrement de la fiabilité du pipeline documentaire.

## 09 — Pipeline documentaire (2:15)

Durée cible : 2 minutes 15.

        Le PDF original est conservé. Docling et l’OCR structurent les pages et les tableaux. Le contenu est normalisé, puis indexé par bge-m3 et FAISS afin de retrouver les passages candidats. L’extraction produit un JSON contraint. Des contrôles vérifient ensuite la page source, l’unité, la période et la cohérence avant validation. Une valeur incertaine est dirigée vers une revue humaine.

        Transition : Ce pipeline s’intègre dans une architecture qui sépare clairement les responsabilités.

## 10 — Architecture générale (1:45)

Durée cible : 1 minute 45.

        L’architecture sépare quatre niveaux. Le frontend React fournit les espaces par rôle. L’API FastAPI expose les fonctions versionnées et applique validation et permissions. Les modules métier isolent les responsabilités. PostgreSQL conserve les données structurées, Redis prépare les traitements asynchrones et le stockage conserve les documents. Le pipeline IA reste un composant remplaçable : Claude, Gemini ou un modèle local peuvent respecter le même schéma de sortie.

        Transition : Chaque technologie a donc été choisie pour une propriété précise du système.

## 11 — Technologies (1:30)

Durée cible : 1 minute 30.

        React et TypeScript structurent les interfaces multi-rôles. FastAPI et Pydantic rendent les contrats d’API explicites. PostgreSQL et SQLModel garantissent l’intégrité et le versionnement. Docling et PaddleOCR comprennent les PDF et les tableaux. bge-m3 et FAISS permettent de mesurer la recherche sémantique indépendamment du modèle génératif. Docker et la CI rendent l’environnement reproductible. Le choix technologique répond donc directement à un besoin de confiance.

        Transition : Ces briques deviennent concrètes dans le parcours de démonstration.

## 12 — Démonstration (3:30)

Durée cible : 3 minutes 30.

        La vidéo suit un seul fil narratif : l’administrateur crée une entreprise, le rapport est déposé et analysé, l’auditeur contrôle les preuves, l’administrateur valide et publie, puis l’investisseur compare les résultats. La démonstration se termine par un aperçu des espaces Chercheur et Institution. Les captures d’écran servent de solution de secours si la vidéo ne démarre pas.

        Transition : Après le parcours fonctionnel, voici les résultats de l’évaluation.

## 13 — Résultats obtenus (2:00)

Durée cible : 2 minutes.

        Le corpus pilote contient Microsoft, Ørsted et Ingka Group : 343 pages et 267 tableaux ont été structurés. Le benchmark de recherche retrouve 11 indicateurs sur 15 dans les huit meilleures pages. Ørsted et Ingka atteignent 100 % sur ce test ; pour Microsoft, la page attendue arrive au rang 10. Ce résultat mesure la récupération documentaire et sert à orienter l’amélioration continue du classement sémantique. L’ensemble du pipeline est intégré au workflow de la plateforme.

        Transition : Ces résultats conduisent aux recommandations et aux perspectives d’évolution.

## 14 — Limites, recommandations et perspectives (1:45)

Durée cible : 1 minute 45.

        Les limites concernent désormais l’environnement d’exploitation : l’hétérogénéité permanente des rapports, la qualité variable des sources et l’évolution des référentiels. Les recommandations sont de maintenir un benchmark continu, une validation humaine ciblée et un versionnement strict des modèles et des règles. Les perspectives portent sur de nouvelles sources ESG et financières, une intelligence multilingue et multimodale, l’automatisation avancée, le traitement distribué et l’interopérabilité avec d’autres systèmes financiers.

        Transition : Ces évolutions prolongent les contributions déjà apportées par le projet.

## 15 — Conclusion (0:45)

Durée cible : 45 secondes.

        GreenFinance Scorer répond à un problème concret : des données ESG dispersées et des scores difficiles à auditer. La plateforme relie chaque résultat à sa source, rend les pondérations configurables, calcule les émissions et l’empreinte financée, puis fournit des analyses adaptées aux différents acteurs. La contribution principale est l’intégration de ces fonctions dans un système ouvert, traçable et explicable.

        Merci. Je suis prêt à répondre à vos questions.
