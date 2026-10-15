"""Pic mémoire enregistré sur chaque exécution d'extraction (dimensionnement de la VM)."""

from pathlib import Path

from app.ingestion.memoire import pic_memoire_mo


def test_lit_le_pic_du_conteneur_quand_cgroup_le_fournit(tmp_path: Path) -> None:
    peak = tmp_path / "memory.peak"
    peak.write_text(f"{3 * 1024 * 1024 * 1024}\n")

    assert pic_memoire_mo(cgroup=peak) == 3072


def test_sans_cgroup_mesure_le_processus(tmp_path: Path) -> None:
    pic = pic_memoire_mo(cgroup=tmp_path / "absent")

    assert pic is not None and pic > 0
