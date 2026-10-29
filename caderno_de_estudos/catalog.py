"""Read the offline study catalog bundled with the desktop app."""

from __future__ import annotations

import json
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parent / "data" / "catalog.json"
EXPECTED_STATUSES = ("Pendente", "Fazendo", "Resolvido")


class CatalogError(ValueError):
    """Raised when the bundled study catalog is incomplete or inconsistent."""


def load_catalog() -> list[dict]:
    """Load the ordered subjects from the app's JSON asset."""
    try:
        payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CatalogError(f"Não foi possível abrir o catálogo local: {error}") from error

    statuses = tuple(payload.get("statuses", ()))
    if statuses != EXPECTED_STATUSES:
        raise CatalogError("O catálogo precisa ter os status Pendente, Fazendo e Resolvido, nessa ordem.")

    subjects = payload.get("subjects")
    if not isinstance(subjects, list) or len(subjects) != 14:
        raise CatalogError("O catálogo precisa conter as 14 matérias da aba Essenciais.")

    keys: set[str] = set()
    for expected_priority, subject in enumerate(subjects, start=1):
        if not isinstance(subject, dict):
            raise CatalogError(f"A matéria de prioridade {expected_priority} está inválida.")
        if subject.get("priority") != expected_priority:
            raise CatalogError("A ordem de prioridade do catálogo precisa acompanhar a aba Essenciais.")
        key = subject.get("key")
        if not isinstance(key, str) or not key or key in keys:
            raise CatalogError(f"A chave da matéria de prioridade {expected_priority} está ausente ou repetida.")
        if not isinstance(subject.get("name"), str) or not subject["name"].strip():
            raise CatalogError(f"O nome da matéria de prioridade {expected_priority} está vazio.")
        for field in ("theory", "practice"):
            if not isinstance(subject.get(field), str):
                raise CatalogError(f"A indicação {field} da matéria {subject['name']} está inválida.")
        for field in ("resources", "books"):
            if not isinstance(subject.get(field), list):
                subject[field] = []
        keys.add(key)

    return subjects
