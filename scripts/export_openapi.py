"""Exporte le schéma OpenAPI de l'API vers frontend/openapi.json, source d'entrée d'Orval.

Ne démarre aucun serveur — construit le schéma directement depuis la sous-application déjà
assemblée (app.api.router:api_app), la même que celle réellement montée sous /api/v1.
Fichier généré, jamais committé (voir frontend/.gitignore) : régénéré par
`npm run api:generate` avant chaque génération du client TypeScript.
"""

import json
from pathlib import Path

from app.api.router import api_app

_OUTPUT = Path(__file__).resolve().parent.parent / "frontend" / "openapi.json"


def main() -> None:
    schema = api_app.openapi()
    _OUTPUT.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OpenAPI exporté vers {_OUTPUT}")


if __name__ == "__main__":
    main()
