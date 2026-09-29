"""Validation des identifiants de marché d'une entreprise (tâche 1.3).

- ISIN (ISO 6166) : 2 lettres de pays, 9 caractères alphanumériques, 1 chiffre de contrôle
  (algorithme de Luhn sur la conversion lettres -> nombres A=10 … Z=35).
- LEI (ISO 17442) : 18 caractères alphanumériques, 2 chiffres de contrôle (ISO 7064 MOD 97-10 :
  la conversion numérique complète vaut 1 modulo 97).

Fonctions pures, sans accès base : l'unicité en base est portée par les contraintes
companies_isin_key / companies_lei_key (tâche 1.1).
"""

import re

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
