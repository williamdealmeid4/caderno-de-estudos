# Caderno de Estudos Implementation Plan

> **For agentic workers:** Use the native execution path and follow the waves in order. No subagents are authorized for this task.

**Goal:** Build an offline Python desktop app for tracking the user's 14 priority-ordered study subjects on Linux and Windows.

**Architecture:** Bundle the workbook-derived subject catalog as JSON. A Tkinter board renders each subject in one of three status columns and writes changes to a per-user SQLite database.

**Tech Stack:** Python 3.11+, Tkinter/ttk, `sqlite3`, `zipfile`, `xml.etree.ElementTree`, and JSON from the standard library.

**Spec:** `docs/superpowers/specs/2026-10-29-caderno-de-estudos-design.md`

## Global Constraints

- The board has exactly three statuses: `Pendente`, `Fazendo`, and `Resolvido`.
- The priority sequence is the order in `Essenciais`, from Algoritmos through Hardware.
- The app must not make network requests or require a browser.
- Use Python 3.11 or newer, Tkinter, and the standard-library `sqlite3` module. Do not add runtime dependencies.
- Store progress in the user's local application-data directory: `$XDG_DATA_HOME/caderno-de-estudos` or `~/.local/share/caderno-de-estudos` on Linux; `%APPDATA%/CadernoDeEstudos` on Windows.
- The app source and launchers must support Linux and Windows. A Python installation with Tk support is required on either system.

## Review Focus

- A subject's status survives app restarts and does not reset when the catalog is initialized again.
- A subject with an unknown saved status falls back safely to `Pendente`.
- A failed database write does not move the card visually while leaving persisted state stale.
- Long subject/resource names remain readable in a narrow column and the column can scroll.
- Missing optional workbook resources do not hide the subject or break the board.

## Ondas de Execução

### Wave 1 — Local catalog and persistence

**Files:**
- Create: `tools/import_workbook.py`
- Create: `caderno_de_estudos/data/catalog.json`
- Create: `caderno_de_estudos/catalog.py`
- Create: `caderno_de_estudos/storage.py`

**Deliverable:** the workbook's 14 ordered subjects and their recommendations are available from bundled JSON; local storage initializes missing statuses and saves/retrieves progress by stable subject key.

**Task 1: Import and validate the workbook catalog**

- [x] Read the workbook's shared strings and four worksheet tables using Python's standard OOXML/ZIP modules.
- [x] Map the 14 `Essenciais` subjects to stable keys and assign the resource and book rows to those subjects.
- [x] Write the generated 14-subject catalog to `caderno_de_estudos/data/catalog.json`.
- [x] Implement `catalog.load_catalog() -> list[dict]` to validate status names, subject keys, and priority order.

**Task 2: Persist subject progress locally**

- [x] Implement `storage.database_path() -> Path` for Linux XDG data and Windows AppData locations.
- [x] Implement `storage.initialize(subjects) -> Path` to create the SQLite table and insert new subjects as `Pendente` without overwriting saved statuses.
- [x] Implement `storage.load_statuses(subjects) -> dict[str, str]` with a safe `Pendente` fallback.
- [x] Implement `storage.save_status(subject_key: str, status: str) -> None` with validation and an immediate SQLite commit.

### Wave 2 — Desktop board

**Files:**
- Create: `caderno_de_estudos/__init__.py`
- Create: `caderno_de_estudos/__main__.py`
- Create: `caderno_de_estudos/ui.py`

**Interfaces:**
- `catalog.load_catalog() -> list[dict]` returns ordered subject records.
- `storage.initialize(subjects) -> Path` creates the local database and inserts missing subjects as `Pendente` without overwriting existing statuses.
- `storage.load_statuses(subjects) -> dict[str, str]` returns status by subject key.
- `storage.save_status(subject_key: str, status: str) -> None` persists one valid status.
- `ui.run() -> None` loads the catalog/database and opens the Tkinter window.

**Deliverable:** a three-column board with priority numbers, per-card status selectors, completion counts, scrolling, and a local material-details window. A successful status update saves before the board redraws.

**Task 3: Render the desktop board and material details**

- [x] Create the Tkinter window with the approved three-column status layout and a completion summary.
- [x] Render all subjects in priority order within their saved status column and allow scrolling in each column.
- [x] Add status selectors that save first, then move the card and refresh counts.
- [x] Add a local details window for the subject's recommendations, workbook resources, and books; keep URLs non-interactive.
- [x] Add Portuguese error feedback when the bundled catalog or local database cannot be opened or saved.

### Wave 3 — Platform launchers and handoff

**Files:**
- Create: `launch_linux.sh`
- Create: `install_linux.sh`
- Create: `launch_windows.bat`
- Create: `README.md`
- Create: `.gitignore`

**Deliverable:** the Linux app can be launched from the desktop applications menu after installation; Windows can launch the same source with Python/Tkinter; README explains offline behavior and local progress-file locations.

**Task 4: Add platform launchers and operating notes**

- [x] Add `launch_linux.sh` and `install_linux.sh` to register a GNOME application-menu entry.
- [x] Add `launch_windows.pyw` and `launch_windows.bat` for a Python/Tkinter installation on Windows.
- [x] Document requirements, offline behavior, progress database locations, and workbook re-import in `README.md`.
- [x] Ignore local bytecode, virtual environments, build outputs, and SQLite databases in `.gitignore`.

## Execution Notes

- The user explicitly requested implementation. Use the inline/native path and the suggested project folder `~/Projetos/caderno-de-estudos`.
- The user did not request tests or verification; do not add or run them.
- Do not commit, publish, or upload the project.
