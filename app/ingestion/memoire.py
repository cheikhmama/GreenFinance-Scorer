"""Pic mémoire d'une exécution d'extraction, enregistré sur ExtractionRun.pic_memoire_mo : c'est la
mesure qui dimensionne la limite mémoire du worker sur la VM (docs/DEPLOIEMENT_ORACLE.md)."""

import sys
from pathlib import Path

# cgroup v2 : pic du conteneur entier (modèles, OCR, tous les threads), ce que la limite mem_limit
# compare — plus juste que le pic du seul processus Python.
CGROUP_MEMORY_PEAK = Path("/sys/fs/cgroup/memory.peak")


def pic_memoire_mo(*, cgroup: Path = CGROUP_MEMORY_PEAK) -> int | None:
    try:
        return int(cgroup.read_text().strip()) // (1024 * 1024)
    except (OSError, ValueError):
        pass
    if sys.platform == "win32":
        return _pic_processus_windows()
    import resource

    # ru_maxrss : kilo-octets sous Linux.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024


def _pic_processus_windows() -> int | None:
    """Développement local seulement (le worker tourne sous Linux)."""
    import ctypes
    from ctypes import wintypes

    class _Compteurs(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32")  # type: ignore[attr-defined]
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.K32GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_Compteurs),
        wintypes.DWORD,
    ]
    kernel32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
    compteurs = _Compteurs()
    compteurs.cb = ctypes.sizeof(_Compteurs)
    if not kernel32.K32GetProcessMemoryInfo(
        kernel32.GetCurrentProcess(), ctypes.byref(compteurs), compteurs.cb
    ):
        return None
    return int(compteurs.PeakWorkingSetSize) // (1024 * 1024)
