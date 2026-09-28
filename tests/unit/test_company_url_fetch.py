from typing import ClassVar

import httpx
import pytest

from app.company.url_fetch import _valider_url_cible, telecharger_pdf_depuis_url
from app.core.exceptions import ValidationError


def test_schema_ftp_est_rejete() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _valider_url_cible("ftp://example.com/rapport.pdf")
    assert exc_info.value.code == "url_schema_invalide"


def test_schema_file_est_rejete() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _valider_url_cible("file:///etc/passwd")
    assert exc_info.value.code == "url_schema_invalide"


def test_hote_manquant_est_rejete() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _valider_url_cible("https:///rapport.pdf")
    assert exc_info.value.code == "url_schema_invalide"


@pytest.mark.parametrize(
    "hote,adresse",
    [
        ("metadata.internal", "169.254.169.254"),  # métadonnées cloud
        ("localhost.test", "127.0.0.1"),
        ("interne.test", "10.0.0.5"),
        ("interne.test", "192.168.1.10"),
        ("interne.test", "172.16.0.1"),
        ("multicast.test", "224.0.0.1"),
    ],
)
def test_adresse_non_routable_est_rejetee(monkeypatch, hote: str, adresse: str) -> None:
    monkeypatch.setattr(
        "app.company.url_fetch.socket.getaddrinfo",
        lambda *_a, **_k: [(None, None, None, None, (adresse, 443))],
    )
    with pytest.raises(ValidationError) as exc_info:
        _valider_url_cible(f"https://{hote}/rapport.pdf")
    assert exc_info.value.code == "url_cible_non_autorisee"


def test_adresse_publique_est_acceptee(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.company.url_fetch.socket.getaddrinfo",
        lambda *_a, **_k: [(None, None, None, None, ("93.184.216.34", 443))],
    )
    _valider_url_cible("https://exemple-public.test/rapport.pdf")  # ne lève pas


def test_resolution_dns_echouee_est_rejetee(monkeypatch) -> None:
    import socket

    def _echec(*_a, **_k):
        raise socket.gaierror("résolution impossible")

    monkeypatch.setattr("app.company.url_fetch.socket.getaddrinfo", _echec)
    with pytest.raises(ValidationError) as exc_info:
        _valider_url_cible("https://inexistant.test/rapport.pdf")
    assert exc_info.value.code == "url_cible_non_autorisee"


def test_telechargement_plafonne_en_flux(monkeypatch) -> None:
    """La taille est vérifiée AU FUR ET À MESURE du flux, jamais après avoir tout bufferisé --
    ce test envoie un contenu déjà au-dessus du plafond pour vérifier le rejet, sans prétendre
    couvrir l'absence de buffer non borné (propriété de conception, pas testable par une assertion
    unitaire simple)."""
    monkeypatch.setattr(
        "app.company.url_fetch.socket.getaddrinfo",
        lambda *_a, **_k: [(None, None, None, None, ("93.184.216.34", 443))],
    )
    monkeypatch.setattr("app.company.url_fetch.TAILLE_MAX_OCTETS", 10)

    class _FausseReponse:
        is_redirect = False
        status_code = 200
        headers: ClassVar[dict] = {}

        def iter_bytes(self):
            yield b"0123456789"
            yield b"encore-trop"

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(httpx, "stream", lambda *_a, **_k: _FausseReponse())

    with pytest.raises(ValidationError) as exc_info:
        telecharger_pdf_depuis_url("https://exemple-public.test/rapport.pdf")
    assert exc_info.value.code == "telechargement_trop_volumineux"


def test_trop_de_redirections_est_rejete(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.company.url_fetch.socket.getaddrinfo",
        lambda *_a, **_k: [(None, None, None, None, ("93.184.216.34", 443))],
    )

    class _FausseRedirection:
        is_redirect = True
        status_code = 302
        headers: ClassVar[dict] = {"location": "https://exemple-public.test/suite.pdf"}

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(httpx, "stream", lambda *_a, **_k: _FausseRedirection())

    with pytest.raises(ValidationError) as exc_info:
        telecharger_pdf_depuis_url("https://exemple-public.test/rapport.pdf")
    assert exc_info.value.code == "telechargement_echoue"


def test_redirection_vers_ip_interne_est_rejetee(monkeypatch) -> None:
    """La cible de chaque saut de redirection est revalidée -- une redirection vers une IP
    interne doit être rejetée même si le premier hôte était public."""
    adresses = iter([[(None, None, None, None, ("93.184.216.34", 443))], [(None, None, None, None, ("169.254.169.254", 443))]])
    monkeypatch.setattr(
        "app.company.url_fetch.socket.getaddrinfo", lambda *_a, **_k: next(adresses)
    )

    class _FausseRedirection:
        is_redirect = True
        status_code = 302
        headers: ClassVar[dict] = {"location": "https://interne.test/secret.pdf"}

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(httpx, "stream", lambda *_a, **_k: _FausseRedirection())

    with pytest.raises(ValidationError) as exc_info:
        telecharger_pdf_depuis_url("https://exemple-public.test/rapport.pdf")
    assert exc_info.value.code == "url_cible_non_autorisee"


def test_delai_depasse_est_signale_explicitement(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.company.url_fetch.socket.getaddrinfo",
        lambda *_a, **_k: [(None, None, None, None, ("93.184.216.34", 443))],
    )

    def _stream_qui_expire(*_a, **_k):
        raise httpx.ConnectTimeout("délai dépassé")

    monkeypatch.setattr(httpx, "stream", _stream_qui_expire)

    with pytest.raises(ValidationError) as exc_info:
        telecharger_pdf_depuis_url("https://exemple-public.test/rapport.pdf")
    assert exc_info.value.code == "telechargement_delai_depasse"


def test_statut_http_non_200_est_rejete(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.company.url_fetch.socket.getaddrinfo",
        lambda *_a, **_k: [(None, None, None, None, ("93.184.216.34", 443))],
    )

    class _FausseReponse404:
        is_redirect = False
        status_code = 404
        headers: ClassVar[dict] = {}

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(httpx, "stream", lambda *_a, **_k: _FausseReponse404())

    with pytest.raises(ValidationError) as exc_info:
        telecharger_pdf_depuis_url("https://exemple-public.test/rapport.pdf")
    assert exc_info.value.code == "telechargement_echoue"
