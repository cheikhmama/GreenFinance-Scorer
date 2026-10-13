"""Serveur MCP (stdio) exposant l'extraction ESG à un agent : extract_esg_report(file_path).

Lancé par l'agent, jamais exposé sur le réseau :

    docker compose --profile mcp run --rm -i -v "$PWD/rapports:/data:ro" mcp

Les fichiers lisibles sont limités à MCP_RACINE_FICHIERS (/data par défaut, le dossier monté) :
un chemin qui en sort est refusé avant toute lecture. Les journaux vont sur stderr — stdout porte le
protocole MCP.
"""

import os
import sys
from collections.abc import Callable
from pathlib import Path

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

from app.company.upload_validation import valider_pdf
from app.core.exceptions import ValidationError
from app.ingestion.cibles import INDICATEURS_CIBLES
from app.ingestion.referentiels import Referentiels, charger_referentiels
from app.ingestion.sortie import Famille, RapportExtraitJSON, famille_du_code

# Fichier local choisi par l'utilisateur de l'agent, pas un dépôt public : plafond plus large que
# les 50 Mo du dépôt web, la mémoire restant bornée par la conversion par lots.
TAILLE_MAX_OCTETS = 300 * 1024 * 1024

Extraire = Callable[..., RapportExtraitJSON]


class IndicateurCatalogue(BaseModel):
    code: str
    famille: Famille
    referentiels: Referentiels


def _extraire_par_defaut(chemin: Path, *, nom_entreprise: str | None, annee: int | None) -> RapportExtraitJSON:
    from app.ingestion.coeur import (
        extraire_document,  # pile d'extraction : chargée au premier appel
    )

    return extraire_document(chemin, nom_entreprise=nom_entreprise, annee=annee)


def _resoudre(racine: Path, file_path: str) -> Path:
    """ToolError : refus attendu, message lu par le modèle (une autre exception n'arriverait que
    comme « Error executing tool »)."""
    racine = racine.resolve()
    chemin = (racine / file_path).resolve()  # un chemin absolu remplace la racine, puis est vérifié
    if not chemin.is_relative_to(racine):
        raise ToolError(f"Chemin hors du dossier autorisé ({racine}) : {file_path}")
    if not chemin.is_file():
        raise ToolError(f"Fichier introuvable : {file_path}")
    try:
        valider_pdf(chemin.read_bytes(), taille_max=TAILLE_MAX_OCTETS)
    except ValidationError as exc:
        raise ToolError(f"PDF refusé : {exc}") from exc
    return chemin


def creer_serveur(racine: Path, *, extraire: Extraire = _extraire_par_defaut) -> MCPServer:
    serveur = MCPServer(
        name="greenfinance-esg",
        instructions=(
            "Extraction d'indicateurs ESG (Scope 1-3, énergie, déchets, social, gouvernance) depuis "
            "un rapport PDF, alignés sur GHG Protocol, GRI et ESRS. Chaque valeur publiée porte sa "
            "page source ; une valeur sans page n'est jamais renvoyée."
        ),
    )

    @serveur.tool()
    async def extract_esg_report(
        file_path: str, company_name: str | None = None, fiscal_year: int | None = None
    ) -> RapportExtraitJSON:
        """Extrait les indicateurs ESG d'un rapport PDF du dossier autorisé (chemin relatif à ce
        dossier, ou absolu à l'intérieur). Long : plusieurs minutes pour un rapport de 200 pages
        (conversion par lots, OCR des pages scannées, appel LLM)."""
        chemin = _resoudre(racine, file_path)
        return await anyio.to_thread.run_sync(
            lambda: extraire(chemin, nom_entreprise=company_name, annee=fiscal_year)
        )

    @serveur.tool()
    def list_esg_indicators() -> list[IndicateurCatalogue]:
        """Catalogue des indicateurs extraits, avec leur correspondance GHG Protocol / GRI / ESRS."""
        referentiels = charger_referentiels()
        return [
            IndicateurCatalogue(code=c.code, famille=famille_du_code(c.code), referentiels=referentiels[c.code])
            for c in INDICATEURS_CIBLES
        ]

    return serveur


def main() -> None:
    import structlog

    # stdout porte le protocole MCP : tout journal (structlog, bibliothèques) va sur stderr.
    structlog.configure(logger_factory=structlog.PrintLoggerFactory(file=sys.stderr))
    racine = Path(os.environ.get("MCP_RACINE_FICHIERS", "/data"))
    creer_serveur(racine).run()


if __name__ == "__main__":
    main()
