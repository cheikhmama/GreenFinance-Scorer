"""Validation des identifiants d'une entreprise : de marché (tâche 1.3) et fiscal (tâche 5.10).

- ISIN (ISO 6166) : 2 lettres de pays, 9 caractères alphanumériques, 1 chiffre de contrôle
  (algorithme de Luhn sur la conversion lettres -> nombres A=10 … Z=35).
- LEI (ISO 17442) : 18 caractères alphanumériques, 2 chiffres de contrôle (ISO 7064 MOD 97-10 :
  la conversion numérique complète vaut 1 modulo 97).

Fonctions pures, sans accès base : l'unicité en base est portée par les contraintes
companies_isin_key / companies_lei_key (tâche 1.1).
"""

import re

from app.core.enums import TaxIdType

_ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
_LEI = re.compile(r"^[A-Z0-9]{18}[0-9]{2}$")


def _en_chiffres(identifiant: str) -> str:
    # int(c, 36) : '0'-'9' -> 0-9, 'A'-'Z' -> 10-35 — la conversion commune aux deux normes.
    return "".join(str(int(caractere, 36)) for caractere in identifiant)


def _luhn_valide(chiffres: str) -> bool:
    total = 0
    for position, caractere in enumerate(reversed(chiffres)):
        chiffre = int(caractere)
        if position % 2 == 1:
            chiffre *= 2
            if chiffre > 9:
                chiffre -= 9
        total += chiffre
    return total % 10 == 0


def isin_valide(isin: str) -> bool:
    return bool(_ISIN.match(isin)) and _luhn_valide(_en_chiffres(isin))


def lei_valide(lei: str) -> bool:
    return bool(_LEI.match(lei)) and int(_en_chiffres(lei)) % 97 == 1


# Identifiant fiscal (tâche 5.10) : sa nature suit le pays, jamais le client.
_TYPE_PAR_PAYS = {"MR": TaxIdType.NIF, "FR": TaxIdType.SIREN, "US": TaxIdType.EIN}


def type_identifiant_fiscal(pays: str) -> TaxIdType:
    return _TYPE_PAR_PAYS.get(pays.upper(), TaxIdType.TAX_ID)


def normaliser_identifiant_fiscal(pays: str, valeur: str) -> tuple[TaxIdType, str]:
    """Nature et forme normalisée de l'identifiant fiscal d'une entreprise de `pays`, ou
    ValueError avec un message lisible :
    - NIF (Mauritanie) : 8 chiffres ;
    - SIREN (France) : 9 chiffres, clé de Luhn ;
    - EIN (États-Unis) : 9 chiffres, rendu « 12-3456789 » ;
    - ailleurs : 3 à 32 caractères alphanumériques (tirets, points et barres obliques admis).
    Les espaces sont ignorés partout."""
    nature = type_identifiant_fiscal(pays)
    propre = re.sub(r"\s+", "", valeur).upper()
    if nature == TaxIdType.NIF:
        if not re.fullmatch(r"\d{8}", propre):
            raise ValueError("Le NIF mauritanien doit comporter exactement 8 chiffres.")
    elif nature == TaxIdType.SIREN:
        if not re.fullmatch(r"\d{9}", propre):
            raise ValueError("Le numéro SIREN doit comporter 9 chiffres.")
        if not _luhn_valide(propre):
            raise ValueError("Numéro SIREN invalide (clé de contrôle).")
    elif nature == TaxIdType.EIN:
        if not re.fullmatch(r"\d{2}-?\d{7}", propre):
            raise ValueError("L'EIN doit comporter 9 chiffres (ex. 12-3456789).")
        chiffres = propre.replace("-", "")
        propre = f"{chiffres[:2]}-{chiffres[2:]}"
    elif not re.fullmatch(r"[A-Z0-9][A-Z0-9./-]{2,31}", propre):
        raise ValueError("Saisissez un identifiant fiscal valide (3 à 32 caractères).")
    return nature, propre
