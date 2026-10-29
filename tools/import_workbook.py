#!/usr/bin/env python3
"""Build the app's offline catalog from the study workbook."""

from __future__ import annotations

import argparse
import json
import posixpath
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"x": MAIN_NS, "r": REL_NS, "p": PKG_REL_NS}

SUBJECT_IDS = {
    "Algoritmos": "algoritmos",
    "Python": "python",
    "Go": "go",
    "Rust": "rust",
    "Frontend": "frontend",
    "Backend e APIs": "backend-apis",
    "SQL": "sql",
    "Git": "git",
    "Linux": "linux",
    "Windows": "windows",
    "Redes": "redes",
    "Cibersegurança": "ciberseguranca",
    "Virtualização": "virtualizacao",
    "Hardware": "hardware",
}

PROGRAMMING_MODULES = {
    "Lógica e algoritmos": "algoritmos",
    "Python": "python",
    "Go": "go",
    "Rust": "rust",
    "Frontend": "frontend",
    "Git e GitHub": "git",
}

SQL_RESOURCES = {"SQLBolt", "PostgreSQL Exercises", "MySQL Documentation"}
WINDOWS_RESOURCES = {"Microsoft Learn PowerShell", "Microsoft Sysinternals", "Windows Server Docs"}
LINUX_SERVER_RESOURCES = {"Ubuntu Server Docs", "Debian Documentation"}
SQL_BOOKS = {"SQL Antipatterns — Bill Karwin", "Learning SQL — Alan Beaulieu"}


def _column_index(cell_ref: str) -> int:
    letters = "".join(char for char in cell_ref if char.isalpha())
    value = 0
    for char in letters:
        value = value * 26 + ord(char.upper()) - ord("A") + 1
    return value - 1


def _shared_strings(archive: ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        "".join(node.text or "" for node in item.findall(".//x:t", NS))
        for item in root.findall("x:si", NS)
    ]


def _cell_text(cell: ET.Element, strings: list[str]) -> str:
    kind = cell.get("t")
    if kind == "inlineStr":
        inline = cell.find("x:is", NS)
        return "" if inline is None else "".join(node.text or "" for node in inline.findall(".//x:t", NS))
    value = cell.find("x:v", NS)
    raw = "" if value is None or value.text is None else value.text
    if kind == "s" and raw:
        return strings[int(raw)]
    return raw


def _sheet_rows(archive: ZipFile, sheet_path: str, strings: list[str]) -> list[dict[str, str]]:
    root = ET.fromstring(archive.read(sheet_path))
    raw_rows: list[list[str]] = []
    for row in root.findall(".//x:sheetData/x:row", NS):
        cells: list[str] = []
        for cell in row.findall("x:c", NS):
            index = _column_index(cell.get("r", "A1"))
            while len(cells) <= index:
                cells.append("")
            cells[index] = _cell_text(cell, strings)
        raw_rows.append(cells)
    if not raw_rows:
        return []
    headers = raw_rows[0]
    result = []
    for values in raw_rows[1:]:
        if not any(values):
            continue
        result.append({header: values[index] if index < len(values) else "" for index, header in enumerate(headers) if header})
    return result


def read_workbook(path: Path) -> dict[str, list[dict[str, str]]]:
    with ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {node.get("Id"): node.get("Target", "") for node in relationships.findall("p:Relationship", NS)}
        strings = _shared_strings(archive)
        sheets: dict[str, list[dict[str, str]]] = {}
        for sheet in workbook.findall("x:sheets/x:sheet", NS):
            relationship_id = sheet.get(f"{{{REL_NS}}}id", "")
            target = targets[relationship_id]
            sheet_path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
            if not sheet_path.startswith("xl/"):
                sheet_path = "xl/" + sheet_path
            sheets[sheet.get("name", "")] = _sheet_rows(archive, sheet_path, strings)
        return sheets


def _resource_subject(row: dict[str, str]) -> str:
    module, title = row.get("Módulo", ""), row.get("Recurso / site", "")
    if module in PROGRAMMING_MODULES:
        return PROGRAMMING_MODULES[module]
    if module == "Backend, APIs, JSON e SQL":
        return "sql" if title in SQL_RESOURCES else "backend-apis"
    if module == "Windows e Linux":
        return "windows" if title in WINDOWS_RESOURCES - {"Windows Server Docs"} else "linux"
    if module == "Virtualização e servidores":
        if title in WINDOWS_RESOURCES:
            return "windows"
        if title in LINUX_SERVER_RESOURCES:
            return "linux"
        return "virtualizacao"
    if module == "Redes, IP e protocolos":
        return "redes"
    if module == "Cibersegurança":
        return "ciberseguranca"
    if module == "Hardware e manutenção":
        return "hardware"
    raise ValueError(f"Módulo de recurso sem destino: {module!r} / {title!r}")


def _book_subject(row: dict[str, str]) -> str:
    module, title = row.get("Módulo", ""), row.get("Título e autor", "")
    if module == "Backend, APIs, JSON e SQL":
        return "sql" if title in SQL_BOOKS else "backend-apis"
    if module == "Windows e Linux":
        return "linux"
    mapping = {
        "Lógica e algoritmos": "algoritmos",
        "Python": "python",
        "Go": "go",
        "Rust": "rust",
        "Frontend": "frontend",
        "Virtualização e servidores": "virtualizacao",
        "Hardware e manutenção": "hardware",
        "Redes, IP e protocolos": "redes",
        "Cibersegurança": "ciberseguranca",
    }
    if module not in mapping:
        raise ValueError(f"Módulo de livro sem destino: {module!r} / {title!r}")
    return mapping[module]


def build_catalog(sheets: dict[str, list[dict[str, str]]]) -> dict:
    essential_rows = sheets.get("Essenciais", [])
    if len(essential_rows) != len(SUBJECT_IDS):
        raise ValueError(f"Esperadas 14 matérias na aba Essenciais; encontrei {len(essential_rows)}.")

    subjects = []
    for priority, row in enumerate(essential_rows, start=1):
        name = row.get("Assunto", "")
        key = SUBJECT_IDS.get(name)
        if key is None:
            raise ValueError(f"Assunto sem identificador estável: {name!r}")
        subjects.append({
            "key": key,
            "priority": priority,
            "name": name,
            "theory": row.get("Teoria recomendada", ""),
            "practice": row.get("Prática recomendada", ""),
            "resources": [],
            "books": [],
        })
    by_key = {subject["key"]: subject for subject in subjects}

    for sheet_name in ("Programação", "Computação"):
        for row in sheets.get(sheet_name, []):
            subject_key = _resource_subject(row)
            by_key[subject_key]["resources"].append({
                "title": row.get("Recurso / site", ""),
                "description": row.get("Conteúdo", ""),
                "type": row.get("Tipo", ""),
                "url": row.get("URL", ""),
                "area": sheet_name,
            })

    for row in sheets.get("Livros", []):
        subject_key = _book_subject(row)
        by_key[subject_key]["books"].append({
            "title": row.get("Título e autor", ""),
            "note": row.get("Observação", ""),
        })

    return {
        "name": "Caderno de estudos",
        "statuses": ["Pendente", "Fazendo", "Resolvido"],
        "subjects": subjects,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path, help="caminho para Biblioteca_Estudos_Programacao_Computacao.xlsx")
    parser.add_argument("--output", type=Path, default=Path("caderno_de_estudos/data/catalog.json"))
    args = parser.parse_args()

    catalog = build_catalog(read_workbook(args.workbook))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total_resources = sum(len(subject["resources"]) for subject in catalog["subjects"])
    total_books = sum(len(subject["books"]) for subject in catalog["subjects"])
    print(f"Criados {len(catalog['subjects'])} cards, {total_resources} recursos e {total_books} livros em {args.output}.")


if __name__ == "__main__":
    main()
