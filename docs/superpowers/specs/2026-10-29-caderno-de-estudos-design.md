# Caderno de Estudos — design

## Intent

Turn the user's programming and computing study workbook into a small desktop app for recording progress. It should open without a browser, work without a network connection, and keep each subject's status after the app closes.

## Goals

- Show the 14 subjects from the workbook's `Essenciais` sheet as cards in a three-column board: `Pendente`, `Fazendo`, and `Resolvido`.
- Preserve the `Essenciais` row order as each subject's priority. Show its number in every status column and sort cards by that number within each column.
- Save a subject's status immediately to a local SQLite database.
- Show the recommended theory and practice on each card. A local details window may show other workbook resources and book recommendations as text; it never opens a URL.
- Run on Linux and Windows without a network connection or third-party runtime packages.

## Non-goals

- Accounts, cloud sync, reminders, due dates, timers, social features, or in-app editing of the study catalog.
- Tracking progress separately for each book or website; a status belongs to a subject.
- Opening websites from the app. The user asked for a local progress register.

## Constraints

- The board has exactly three statuses: `Pendente`, `Fazendo`, and `Resolvido`.
- The priority sequence is the order in `Essenciais`, from Algoritmos through Hardware.
- The app must not make network requests or require a browser.
- Use Python 3.11 or newer, Tkinter, and the standard-library `sqlite3` module. Do not add runtime dependencies.
- Store progress in the user's local application-data directory: `$XDG_DATA_HOME/caderno-de-estudos` or `~/.local/share/caderno-de-estudos` on Linux; `%APPDATA%/CadernoDeEstudos` on Windows.
- The app source and launchers must support Linux and Windows. A Python installation with Tk support is required on either system.

## Approaches

1. **Python desktop app with Tkinter and SQLite — chosen.** It opens as its own window, works on both requested systems, uses the Python installation already available on this computer, and needs no network at runtime. It keeps packaging and maintenance small. The tradeoff is that Python with Tk must be installed on a Windows machine.
2. **Tauri desktop app with SQLite.** It can produce polished native-window packages for Linux and Windows, but requires a Rust toolchain and more platform-specific packaging work for this small, local register.
3. **Enhanced spreadsheet.** It would remain offline and use the existing file, but it would not provide the selected three-column card board as a standalone app.

## Decisions already made

- The user chose a multiplatform desktop app for Linux and Windows.
- The user selected the board grouped by status in the visual comparison.
- The user approved the `Essenciais` sequence as the priority order.
- The primary cards represent subjects, not individual resources. Status therefore tracks a whole subject.
- Keep the app focused on progress: show the curated theory/practice recommendations on each card and expose the remaining resource and book names in a local details window. Do not make links clickable.
- Default every subject to `Pendente`; preserve saved statuses on later launches.

## Visual direction

The app should feel like a compact study log for programming and computing, rather than a web dashboard. Use the real ordered subject names and workbook recommendations throughout.

### Tokens

- Canvas: `#F3F6F4`, a cool, low-glare background.
- Card: `#FFFFFF`, reserved for study subjects.
- Ink: `#223239`, for readable text and headings.
- Progress teal: `#187F77`, for the active status and resolved count.
- Priority amber: `#C99032`, only for the numbered priority marker.
- Divider: `#DCE5E1`, for quiet column and card boundaries.
- Type: system UI fonts through Tk's default and heading fonts, so the app does not depend on bundled fonts.
- Layout: left-aligned title and completion summary above three equally sized, independently scrollable status columns. A slim amber number rail makes priority visible after cards move between columns. Each card shows its subject, the two essential recommendations, and a status selector.

```text
Caderno de estudos                          0 de 14 resolvidas

┌ Pendente · 14 ─────┬ Fazendo · 0 ─────┬ Resolvido · 0 ────┐
│ 01  Algoritmos      │                  │                   │
│     Entendendo...   │                  │                   │
│     Beecrowd        │                  │                   │
│     Status: ...     │                  │                   │
│ 02  Python          │                  │                   │
│     ...             │                  │                   │
└────────────────────┴──────────────────┴───────────────────┘
```

### Principles

- Priority numbers carry meaning because `Essenciais` is a real recommended sequence.
- Status is the main action; changing it moves the card and saves immediately.
- Keep subject and material text legible before adding decorative elements.
- Use keyboard-accessible status controls and visible focus. Avoid drag-and-drop so each status change is explicit.

## Builder decisions

- Use a bundled JSON catalog generated from the workbook. The runtime reads that catalog and the local SQLite file; it does not need to open the `.xlsx` file.
- Use a stable subject key in SQLite so changing a display label later will not lose progress.
- Add a Linux `.desktop` installer and a Windows `.bat` launcher. Document the Python/Tkinter prerequisite and the local database locations.
- No automated tests or verification commands are included in this task.
