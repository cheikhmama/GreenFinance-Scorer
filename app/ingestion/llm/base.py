"""Erreurs communes aux fournisseurs LLM de l'extraction.

Le pipeline (app/ingestion/extractor.py) ne classe que ces trois cas, quel que soit le fournisseur :
une erreur transitoire remet le job en file, un quota journalier épuisé bascule sur le modèle de
secours puis échoue clairement, une réponse invalide est une erreur d'extraction. Toute autre
exception (clé refusée, modèle inconnu…) remonte telle quelle : réessayer ne la résoudrait pas.
"""


class ErreurLLMTransitoire(Exception):
    """Surcharge, erreur serveur, réseau ou limite par minute persistante : réessayer plus tard."""


class QuotaLLMEpuise(Exception):
    """Quota journalier du modèle épuisé : rien ne passera avant le lendemain sur ce modèle."""


class ReponseLLMInvalide(ValueError):
    """Le modèle n'a pas appelé l'outil, ou ses arguments ne respectent pas le schéma."""


class ContexteLLMTropGrand(Exception):
    """Requête refusée car au-delà de la limite de tokens du fournisseur (413) : réessayer à
    l'identique échouerait pareil — réduire LLM_CONTEXT_TOKENS."""
