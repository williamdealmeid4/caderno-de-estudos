# Registro de estudo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completar o Caderno de Estudos com tema escuro, anotações por matéria e três modos de acompanhar o tempo, mantendo o app local e offline.

**Architecture:** Manter o quadro Tkinter existente e ampliar o SQLite por meio de uma inicialização/migração idempotente. Uma janela de detalhes por matéria terá as abas Materiais, Anotações e Tempo; o estado de tempo é independente por matéria e o modo ativo seleciona qual resumo aparece no card.

**Tech Stack:** Python 3.11+, Tkinter/ttk, sqlite3 e módulos da biblioteca padrão.

**Spec:** `docs/superpowers/specs/2026-10-29-registro-de-estudo-design.md`

## Global Constraints

- Continuar sendo um app desktop multiplataforma para Linux e Windows, executado offline.
- Continuar usando Python, Tkinter e SQLite da biblioteca padrão.
- Manter o tema escuro fixo em todas as janelas, diálogos, campos de edição e abas; não oferecer tema claro.
- Manter dados sob o diretório local de aplicação já usado em cada sistema.
- Tratar duração como minutos inteiros no armazenamento; a interface pode receber horas e minutos e apresentar os valores em formato legível.
- Uma estimativa não preenchida significa que o tempo restante é desconhecido, não zero.
- Cada matéria usa um único modo de acompanhamento de tempo por vez; ao trocar de modo, os dados anteriores ficam armazenados para não serem perdidos.
- O status da matéria continua sendo uma decisão manual e não muda automaticamente quando as horas estimadas forem atingidas.
- Não adicionar nem executar testes sem solicitação do usuário.

## Review Focus

- A migração abre um banco existente sem resetar estados salvos em `progress`.
- Durações vazias continuam desconhecidas e entradas negativas, fracionárias inválidas ou zero para uma sessão não corrompem o registro.
- Trocar o modo por matéria preserva estimativas, sessões, restante manual e data dos modos inativos.
- Um salvamento pendente de anotação é gravado antes que sua janela seja destruída.
- Contraste, foco e conteúdo de todas as janelas pertencentes ao app continuam escuros, inclusive confirmação de remoção de sessão.

---

## Ondas de Execução

- **Onda 1 — Persistência:** Task 1. Define e entrega o contrato SQLite consumido pelas tarefas de interface.
- **Onda 2 — Interface de detalhes:** Task 2. Consome as operações SQLite da Onda 1 e entrega notas, materiais e os três modos de tempo na janela do tema.
- **Onda 3 — Quadro:** Task 3 integra os dados persistidos ao quadro e à inicialização, depois das operações da Onda 1 e da janela da Onda 2.
- **Onda 4 — Documentação:** Task 4 documenta a experiência final depois que o fluxo de interface estiver definido.

Execução Native aprovada pelo usuário; tarefas serão feitas pelo agente principal, sem subagentes.

## Arquivos e responsabilidades

- Modify `caderno_de_estudos/storage.py`: schema/migração idempotente e operações SQLite para dados da matéria, anotações e sessões.
- Modify `caderno_de_estudos/ui.py`: cores escuras, resumo por card, novas abas, formulários, salvamento automático de anotações e diálogos escuros do app.
- Modify `README.md`: documentação dos novos registros, dos modos de tempo e de como os dados seguem guardados localmente.
- Create no runtime files or dependencies. The workbook catalog and launchers remain unchanged.

### Task 1: Persistência de notas e modos de tempo

**Files:**
- Modify: `caderno_de_estudos/storage.py`

**Interfaces:**
- `load_subject_details(subject_keys: Iterable[str], path: Path | None = None) -> dict[str, dict]` returns, per key, `notes`, `time_mode`, `planned_minutes`, `manual_remaining_minutes`, and `target_date`, using empty notes, `sessions`, and `None` values as defaults.
- `save_notes(subject_key: str, notes: str, path: Path | None = None) -> None` writes one subject's notes.
- `save_time_settings(subject_key: str, time_mode: str, value: int | str | None, path: Path | None = None) -> None` validates and saves the selected mode's value while leaving values for the other two modes intact. `sessions` uses planned minutes, `manual` uses remaining minutes, and `date` uses an ISO date.
- `load_sessions(subject_key: str, path: Path | None = None) -> list[dict]` returns sessions newest first with `session_id`, `duration_minutes`, and `studied_at`.
- `load_session_totals(subject_keys: Iterable[str], path: Path | None = None) -> dict[str, int]` returns the sum of logged minutes per requested key, defaulting to zero.
- `add_session(subject_key: str, duration_minutes: int, studied_at: str, path: Path | None = None) -> int` inserts one positive-duration session and returns its id.
- `delete_session(session_id: int, path: Path | None = None) -> None` removes only the selected session.

- [x] Add idempotent `subject_details` and `study_sessions` schema creation inside `initialize`, retaining existing `progress` rows and creating default details rows for new catalog subjects.
- [x] Implement load/save operations above; validate time modes against `sessions`, `manual`, `date`, durations as nonnegative integer minutes where applicable, and ISO dates for `target_date` / `studied_at`.
- [x] Implement `load_session_totals` with a grouped query so board summaries do not need to load full session histories.
- [x] Ensure mode changes update only `time_mode`; preserve the values entered for the other two modes and all existing sessions.
- [x] Review the migration and SQL statements for repeated initialization, absent rows, and existing SQLite data; do not add or run tests.
- [x] Commit this storage deliverable as `feat(storage): add topic notes and time tracking`.

### Task 2: Dark theme and per-topic details window

**Files:**
- Modify: `caderno_de_estudos/ui.py`

**Interfaces:**
- `run()` loads subject details with `load_subject_details`; `StudyBoard.__init__` receives subjects, statuses, and that mapping. Session totals remain optional until Task 3; full session lists load as the Tempo tabs open.
- Replace the materials-only action with `_show_subject_details(subject: dict) -> None`.
- Add focused handlers to parse duration input, save mode settings, save notes, add/remove sessions, and render each active time mode.
- Add an app-owned themed confirmation/error dialog helper in `ui.py` for actions that otherwise use platform-native light message boxes.

- [x] Replace light palette entries in `COLORS` and ttk styles with the approved dark tokens; apply them to board, cards, text views, read-only controls, Notebook tabs, scrollbars, focus states, and app-owned dialogs.
- [x] Build the detail window as a `ttk.Notebook` with `Materiais`, `Anotações`, and `Tempo`; retain the existing workbook resource text in Materiais and never open URLs.
- [x] Add per-topic note editing with a short `after` debounce, a visible `Salvando…`/`Salvo` state, and a close handler that flushes the latest text before destroying the window; if the final save fails, report it and leave the window open.
- [x] Add a `Tempo` mode selector with exactly `Horas previstas + sessões`, `Horas restantes manualmente`, and `Data de conclusão`; display only the active mode's fields and preserve values of inactive modes.
- [x] In sessions mode, accept planned hours/minutes, accept session duration plus a date defaulting to today, list recent sessions, remove a selected session after dark themed confirmation, and show accumulated and remaining time. Remaining is `max(planned - logged, 0)`; signal when logged time exceeds the plan.
- [x] In manual mode, accept nonnegative remaining hours/minutes. In date mode, accept a calendar date and display days remaining or overdue. Do not calculate a date automatically or create reminders.
- [x] Keep subject status changes independent from time tracking and ensure saving any detail refreshes the relevant card summary.
- [x] Commit this detail-window deliverable as `feat(ui): add dark topic details and tracking`.

### Task 3: Board summaries and startup wiring

**Files:**
- Modify: `caderno_de_estudos/ui.py`

**Interfaces:**
- `run()` calls `initialize`, then loads statuses and per-topic details from the same `database_path`.
- `run()` loads `session_minutes_by_subject: dict[str, int]` via `load_session_totals`; the board formats per-card time and overall session summaries from this mapping.
- Card summary text is derived from the current mode for that subject and omits time when no value has been supplied.

- [x] Pass loaded details and per-subject session totals into `StudyBoard` and preserve the existing priority sort and three status columns.
- [x] Show the active time mode's concise summary on each card: planned/logged/remaining for sessions, manual remaining for manual mode, and target date plus day difference for date mode.
- [x] Extend the header summary with total time logged while retaining resolved-subject count and progress bar.
- [x] Review error handling for database failures during startup, note save, mode save, session insertion and removal; use dark app-owned dialogs.
- [x] Commit this board deliverable as `feat(ui): show topic time summaries`.

### Task 4: User documentation

**Files:**
- Modify: `README.md`
- Include: `docs/superpowers/specs/2026-10-29-registro-de-estudo-design.md`
- Include: `docs/superpowers/plans/2026-10-29-registro-de-estudo.md`

- [x] Document that each topic has its own notes and Tempo tab with one active tracking mode at a time.
- [x] Explain how session duration/remaining estimates and date targets are displayed, including that changing modes preserves inactive values.
- [x] Keep offline operation, Linux/Windows launch instructions, SQLite locations, and workbook import instructions accurate.
- [x] Keep the approved design and this plan in the repository as project documentation.
- [x] Review the README against the implemented UI and local database behavior; do not add or run tests.
- [x] Commit documentation as `docs: explain study notes and time tracking`.

## Completion Review

- Review the diff against every criterion in the design doc, especially dark surfaces, per-topic independence, preservation of current statuses, and retention of inactive time-mode data.
- Keep the change dependency-free and ensure the app-owned UI never requires a browser or network connection.
- Automated and manual tests are intentionally omitted unless the user asks for verification.
- Push the finished commits to the existing public `main` repository, as already requested.
