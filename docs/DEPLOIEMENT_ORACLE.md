# Déploiement sur Oracle Cloud Always Free (VM ARM)

Cible : une VM **Ampere A1, 4 OCPU / 24 Go**, Ubuntu 24.04 (aarch64), de l'offre Always Free.
Toute la plateforme y tourne avec `docker compose` : API, workers, Postgres, Redis et Caddy
(frontend + TLS). Le LLM d'extraction est un modèle ouvert servi par un palier gratuit
OpenAI-compatible (Groq, OpenRouter). Rien n'est facturé tant que la VM reste dans l'offre gratuite.

## 1. Budget mémoire

Voir `docker-compose.prod.yml` : environ 16 Go en régime établi.

| Service | mem_limit | cpus |
|---|---|---|
| db (Postgres + pgvector) | 2g | 1 |
| redis | 256m | 0.25 |
| api (2 workers uvicorn) | 768m | 1 |
| worker (e-mails, PDF de synthèse) | 768m | 0.5 |
| worker-extraction | 12g (swap 14g) | 3 |
| caddy | 128m | 0.25 |

Le pic du worker d'extraction dépend de la **taille d'un lot** de pages
(`EXTRACTION_PAGES_PAR_LOT`, 20 par défaut), pas de la longueur du rapport. Chaque exécution
enregistre son pic dans `extraction_runs.pic_memoire_mo` : c'est la mesure à suivre.

## 2. Préparer la VM

```bash
# Docker (dépôt officiel) et le plugin compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER" && newgrp docker

# Fichier d'échange de 4 Go : filet de sécurité, pas de la mémoire de travail
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Ports 80/443 : liste de sécurité du VCN (console OCI) ET pare-feu de l'image Ubuntu d'Oracle
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## 3. Configurer

```bash
git clone <dépôt> greenfinance && cd greenfinance
cp .env.example .env
```

Dans `.env` :

- `ENVIRONMENT=production`, `SECRET_KEY` (au moins 32 octets aléatoires), `FRONTEND_BASE_URL` et
  `CORS_ALLOWED_ORIGINS` sur le domaine public, ainsi que `SMTP_*`.
- LLM :
  - `LLM_PROVIDER=openai_compat`
  - `LLM_BASE_URL=https://api.groq.com/openai/v1`
  - `LLM_API_KEY=<clé Groq>`
  - `LLM_MODEL=llama-3.3-70b-versatile`
  - `LLM_MODEL_SECOURS=llama-3.1-8b-instant`
- `LLM_CONTEXT_TOKENS` : à régler sous la limite de **tokens par minute** du palier, prompt et
  réponse compris. Par exemple `6000` pour un palier à 12 000 TPM. En dessous de 24 000, le pipeline
  fait un appel par famille d'indicateurs (carbone, environnement, social, gouvernance).
  **Vérifier les limites du palier au moment du déploiement** (elles changent) :
  - tokens et requêtes par minute ;
  - tokens par jour : un quota journalier épuisé bascule sur `LLM_MODEL_SECOURS`, puis l'extraction
    échoue avec la cause `quota_llm_epuise`.

Variables du déploiement, à mettre dans l'environnement ou dans `.env` :

```bash
export POSTGRES_PASSWORD=... REDIS_PASSWORD=... DOMAINE=esg.exemple.org
```

## 4. Construire et démarrer

Les images sont construites **sur la VM** (arm64 natif). Celle du worker télécharge à la
construction les modèles Docling, l'OCR ONNX et bge-m3 (plusieurs Go, une seule fois) ; ensuite le
worker démarre hors ligne.

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps   # api « healthy »
docker stats --no-stream                                             # mémoire par service
```

Vérification de bout en bout : déposer un rapport depuis l'espace Entreprise, attendre qu'il
quitte l'état « extraction en cours », puis lire les mesures de son exécution (elles ne sont pas
encore affichées dans l'espace Admin) :

```bash
docker compose exec db psql -U greenfinance -c \
  "select started_at, status, error, pages, pages_ocr, duree_conversion_s, duree_llm_s, pic_memoire_mo
   from extraction_runs order by started_at desc limit 5;"
```

## 5. Réglages pour les longs rapports (200 pages et plus)

| Variable | Défaut | Effet |
|---|---|---|
| `EXTRACTION_PAGES_PAR_LOT` | 20 | Pages converties à la fois. Le baisser (10) réduit le pic mémoire ; le monter accélère un peu. |
| `EXTRACTION_THREADS` | 3 | Threads Docling, ONNX et torch. À aligner sur `cpus` du worker. |
| `EXTRACTION_PAGES_MAX` | 600 | Au-delà, refus immédiat (cause `document_trop_long`). |
| `EXTRACTION_TIMEOUT_MINUTES` | 180 | Délai d'un job ; la supervision clôt une exécution bloquée au-delà. |

Une extraction interrompue (délai dépassé, conteneur tué faute de mémoire, redémarrage) reprend à
partir des lots déjà convertis, conservés dans `storage/docling_json/<rapport>/`.

### Mesurer avant de fixer les limites

```bash
# Rapport synthétique de 250 pages (2 colonnes, tableaux imbriqués, 10 pages scannées) + vérité terrain
docker compose run --rm --no-deps -v "$PWD/scripts:/code/scripts:ro" -v "$PWD/bench:/bench" \
  worker-extraction python scripts/generate_large_esg_pdf.py /bench/synthetique-250p

# Une ligne CSV par exécution : durée, pages par minute, pages OCR, pic mémoire
for lot in 10 20 40; do
  docker compose run --rm --no-deps -v "$PWD/scripts:/code/scripts:ro" -v "$PWD/bench:/bench" \
    worker-extraction python scripts/bench_extraction_memoire.py \
      /bench/synthetique-250p/rapport.pdf --lot "$lot" --threads 3 --csv /bench/resultats.csv
done
```

Le pic mesuré est celui du cgroup du conteneur (`memory.peak`). Pour qu'il reflète la limite réelle,
lancer le banc avec les mêmes `--memory` et `--cpus` que le service.

## 6. Outil MCP `extract_esg_report`

Le serveur MCP (`app/mcp/serveur.py`) expose l'extraction à un agent, en stdio, sans réseau ni base
de données :

```bash
mkdir -p rapports && cp mon-rapport.pdf rapports/
docker compose --profile mcp build mcp
docker compose --profile mcp run --rm -i --no-deps -v "$PWD/rapports:/data:ro" mcp
```

Pour Claude Code, copier `.mcp.json.example` en `.mcp.json`. Deux outils :

- `extract_esg_report(file_path, company_name?, fiscal_year?)` : chemin relatif au dossier monté.
  Renvoie le JSON `RapportExtraitJSON` (`app/ingestion/sortie.py`) :
  - les indicateurs avec leur page source et leur correspondance GHG Protocol, GRI et ESRS ;
  - la couverture de chaque code ;
  - le contexte d'exécution : modèle, durées, pic mémoire.
- `list_esg_indicators()` : le catalogue des 23 indicateurs et leurs référentiels.

Le service partage le budget mémoire du worker d'extraction : sur la VM, ne le lancer que quand
celui-ci est inactif.
