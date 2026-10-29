"""Tkinter interface for the offline study board."""

from __future__ import annotations

import sqlite3
import tkinter as tk
import tkinter.font as tkfont
from datetime import date
from tkinter import ttk

from .catalog import CatalogError, EXPECTED_STATUSES, load_catalog
from .storage import (
    TIME_MODES,
    add_session,
    delete_session,
    initialize,
    load_session_totals,
    load_sessions,
    load_statuses,
    load_subject_details,
    save_notes,
    save_status,
    save_time_settings,
)

COLORS = {
    "canvas": "#171C1F",
    "card": "#242B2E",
    "input": "#1B2225",
    "ink": "#E7ECEA",
    "muted": "#A2B0AA",
    "teal": "#63C6B3",
    "amber": "#E2AE55",
    "line": "#394447",
    "pending": "#30393B",
    "doing": "#453B29",
    "resolved": "#25423A",
    "danger": "#E28C83",
    "selection": "#315D56",
}

COUNT_STYLE = {
    "Pendente": "CountPending.TLabel",
    "Fazendo": "CountDoing.TLabel",
    "Resolvido": "CountResolved.TLabel",
}

STATUS_COLUMNS = (
    ("Pendente", "PENDENTE"),
    ("Fazendo", "FAZENDO"),
    ("Resolvido", "RESOLVIDO"),
)

MODE_LABELS = {
    "sessions": "Horas previstas + sessões",
    "manual": "Horas restantes manualmente",
    "date": "Data de conclusão",
}
MODE_VALUES = {label: mode for mode, label in MODE_LABELS.items()}


def _show_app_dialog(
    parent: tk.Misc,
    title: str,
    message: str,
    *,
    confirm: bool = False,
    confirm_label: str = "Confirmar",
) -> bool:
    """Show an app-owned dark message or confirmation window."""
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.configure(background=COLORS["canvas"])
    dialog.transient(parent)
    dialog.resizable(False, False)
    dialog.geometry("460x190" if confirm else "460x170")

    body = tk.Frame(dialog, background=COLORS["canvas"], padx=22, pady=18)
    body.pack(fill="both", expand=True)
    tk.Label(
        body,
        text=message,
        background=COLORS["canvas"],
        foreground=COLORS["ink"],
        justify="left",
        wraplength=410,
        font=(tkfont.nametofont("TkDefaultFont").actual("family"), 10),
    ).pack(fill="both", expand=True, anchor="w")

    buttons = tk.Frame(body, background=COLORS["canvas"])
    buttons.pack(fill="x", pady=(14, 0))
    result = {"confirmed": False}

    def close(value: bool) -> None:
        result["confirmed"] = value
        dialog.destroy()

    if confirm:
        tk.Button(
            buttons,
            text="Cancelar",
            command=lambda: close(False),
            background=COLORS["card"],
            foreground=COLORS["ink"],
            activebackground=COLORS["line"],
            activeforeground=COLORS["ink"],
            relief="flat",
            padx=12,
            pady=7,
            borderwidth=0,
        ).pack(side="right", padx=(8, 0))
    tk.Button(
        buttons,
        text=confirm_label if confirm else "Entendi",
        command=lambda: close(True),
        background=COLORS["teal"],
        foreground=COLORS["canvas"],
        activebackground="#7DD5C2",
        activeforeground=COLORS["canvas"],
        relief="flat",
        padx=14,
        pady=7,
        borderwidth=0,
        font=(tkfont.nametofont("TkDefaultFont").actual("family"), 9, "bold"),
    ).pack(side="right")

    dialog.protocol("WM_DELETE_WINDOW", lambda: close(False))
    dialog.bind("<Escape>", lambda _event: close(False))
    dialog.grab_set()
    dialog.focus_set()
    parent.wait_window(dialog)
    return result["confirmed"]


def _format_duration(minutes: int | None) -> str:
    if minutes is None:
        return "—"
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours}h {remainder:02d}min"
    if hours:
        return f"{hours}h"
    return f"{remainder}min"


class ScrollableColumn(ttk.Frame):
    def __init__(self, parent: tk.Misc, status: str, heading: str) -> None:
        super().__init__(parent, style="Column.TFrame")
        self.status = status
        self.count_var = tk.StringVar(value="0")

        heading_row = ttk.Frame(self, style="Column.TFrame")
        heading_row.pack(fill="x", padx=12, pady=(10, 8))
        ttk.Label(heading_row, text=heading, style="ColumnHeading.TLabel").pack(side="left")
        self.count_label = ttk.Label(
            heading_row,
            textvariable=self.count_var,
            style=COUNT_STYLE[status],
            anchor="center",
            width=3,
        )
        self.count_label.pack(side="right")

        self.canvas = tk.Canvas(
            self,
            background=COLORS["canvas"],
            highlightthickness=0,
            borderwidth=0,
        )
        self.scrollbar = ttk.Scrollbar(
            self,
            orient="vertical",
            command=self.canvas.yview,
            style="Vertical.TScrollbar",
        )
        self.cards_frame = ttk.Frame(self.canvas, style="Column.TFrame")
        self.cards_window = self.canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        self.scrollbar.pack(side="right", fill="y", padx=(0, 4), pady=(0, 8))

        self.cards_frame.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._sync_inner_width)

    def _sync_scroll_region(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_inner_width(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.cards_window, width=event.width)

    def contains_pointer(self, x: int, y: int) -> bool:
        left, top = self.canvas.winfo_rootx(), self.canvas.winfo_rooty()
        return left <= x <= left + self.canvas.winfo_width() and top <= y <= top + self.canvas.winfo_height()


class StudyBoard:
    def __init__(
        self,
        root: tk.Tk,
        subjects: list[dict],
        statuses: dict[str, str],
        subject_details: dict[str, dict],
        session_minutes_by_subject: dict[str, int] | None = None,
    ) -> None:
        self.root = root
        self.subjects = subjects
        self.statuses = statuses
        self.subject_details = subject_details
        self.session_minutes_by_subject = session_minutes_by_subject or {
            subject["key"]: 0 for subject in subjects
        }
        self.columns: dict[str, ScrollableColumn] = {}
        self.column_counts: dict[str, tk.StringVar] = {}
        self.completed_var = tk.StringVar()
        self.total_time_var = tk.StringVar()
        self.progress_var = tk.DoubleVar(value=0)
        self.detail_windows: dict[str, tk.Toplevel] = {}
        self.note_editors: dict[str, dict] = {}
        self.time_tabs: dict[str, dict] = {}

        self._configure_window()
        self._configure_styles()
        self._build_shell()
        self._render_board()
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.root.bind_all("<Button-4>", self._on_linux_mousewheel)
        self.root.bind_all("<Button-5>", self._on_linux_mousewheel)

    def _configure_window(self) -> None:
        self.root.title("Caderno de estudos")
        self.root.geometry("1120x760")
        self.root.minsize(920, 620)
        self.root.configure(background=COLORS["canvas"])

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        system_family = tkfont.nametofont("TkDefaultFont").actual("family")
        heading_family = tkfont.nametofont("TkHeadingFont").actual("family")
        if "clam" in style.theme_names():
            style.theme_use("clam")
        self.root.option_add("*TCombobox*Listbox.background", COLORS["input"])
        self.root.option_add("*TCombobox*Listbox.foreground", COLORS["ink"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", COLORS["selection"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", COLORS["ink"])

        style.configure(".", background=COLORS["canvas"], foreground=COLORS["ink"])
        style.configure("TFrame", background=COLORS["canvas"])
        style.configure("App.TFrame", background=COLORS["canvas"])
        style.configure("Column.TFrame", background=COLORS["canvas"])
        style.configure("Card.TFrame", background=COLORS["card"])
        style.configure("TLabel", background=COLORS["canvas"], foreground=COLORS["ink"], font=(system_family, 9))
        style.configure("ColumnHeading.TLabel", background=COLORS["canvas"], foreground=COLORS["ink"], font=(system_family, 10, "bold"))
        style.configure("CountPending.TLabel", background=COLORS["pending"], foreground=COLORS["ink"], font=(system_family, 9, "bold"), padding=(4, 2))
        style.configure("CountDoing.TLabel", background=COLORS["doing"], foreground="#F4D58D", font=(system_family, 9, "bold"), padding=(4, 2))
        style.configure("CountResolved.TLabel", background=COLORS["resolved"], foreground=COLORS["teal"], font=(system_family, 9, "bold"), padding=(4, 2))
        style.configure("Title.TLabel", background=COLORS["canvas"], foreground=COLORS["ink"], font=(heading_family, 20, "bold"))
        style.configure("Subtitle.TLabel", background=COLORS["canvas"], foreground=COLORS["muted"], font=(system_family, 10))
        style.configure("Summary.TLabel", background=COLORS["canvas"], foreground=COLORS["teal"], font=(system_family, 10, "bold"))
        style.configure("CardTitle.TLabel", background=COLORS["card"], foreground=COLORS["ink"], font=(system_family, 11, "bold"))
        style.configure("CardText.TLabel", background=COLORS["card"], foreground=COLORS["muted"], font=(system_family, 9))
        style.configure("Priority.TLabel", background=COLORS["amber"], foreground="#231C0D", font=(system_family, 9, "bold"), padding=(6, 3))
        style.configure("Hint.TLabel", background=COLORS["canvas"], foreground=COLORS["muted"], font=(system_family, 9))
        style.configure("CardHint.TLabel", background=COLORS["card"], foreground=COLORS["muted"], font=(system_family, 9))
        style.configure("CardTime.TLabel", background=COLORS["card"], foreground=COLORS["teal"], font=(system_family, 9, "bold"))
        style.configure("FormHeading.TLabel", background=COLORS["canvas"], foreground=COLORS["ink"], font=(system_family, 10, "bold"))
        style.configure("StatusLine.TLabel", background=COLORS["canvas"], foreground=COLORS["muted"], font=(system_family, 9))
        style.configure("Board.TCombobox", padding=(4, 3), font=(system_family, 9))
        style.map(
            "Board.TCombobox",
            fieldbackground=[("readonly", COLORS["input"])],
            foreground=[("readonly", COLORS["ink"])],
            selectbackground=[("readonly", COLORS["selection"])],
            selectforeground=[("readonly", COLORS["ink"])],
        )
        style.configure("TEntry", fieldbackground=COLORS["input"], foreground=COLORS["ink"], bordercolor=COLORS["line"], lightcolor=COLORS["line"], darkcolor=COLORS["line"], padding=(6, 5))
        style.configure("TButton", background=COLORS["card"], foreground=COLORS["ink"], borderwidth=0, padding=(10, 6), font=(system_family, 9))
        style.map("TButton", background=[("active", COLORS["line"]), ("disabled", COLORS["card"])], foreground=[("disabled", COLORS["muted"])])
        style.configure("Primary.TButton", background=COLORS["teal"], foreground=COLORS["canvas"], borderwidth=0, padding=(10, 6), font=(system_family, 9, "bold"))
        style.map("Primary.TButton", background=[("active", "#7DD5C2")], foreground=[("active", COLORS["canvas"])])
        style.configure("Materials.TButton", background=COLORS["card"], foreground=COLORS["teal"], font=(system_family, 9, "bold"), borderwidth=0, padding=(2, 4))
        style.map("Materials.TButton", background=[("active", COLORS["card"])], foreground=[("active", COLORS["ink"])])
        style.configure("TNotebook", background=COLORS["canvas"], borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure("TNotebook.Tab", background=COLORS["card"], foreground=COLORS["muted"], padding=(14, 8), font=(system_family, 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", COLORS["canvas"]), ("active", COLORS["line"])], foreground=[("selected", COLORS["teal"]), ("active", COLORS["ink"])])
        style.configure("Dark.Treeview", background=COLORS["card"], fieldbackground=COLORS["card"], foreground=COLORS["ink"], rowheight=28, borderwidth=0, font=(system_family, 9))
        style.configure("Dark.Treeview.Heading", background=COLORS["line"], foreground=COLORS["ink"], font=(system_family, 9, "bold"), relief="flat")
        style.map("Dark.Treeview", background=[("selected", COLORS["selection"])], foreground=[("selected", COLORS["ink"])])
        style.configure("Vertical.TScrollbar", background=COLORS["card"], troughcolor=COLORS["canvas"], bordercolor=COLORS["canvas"], arrowcolor=COLORS["muted"], darkcolor=COLORS["card"], lightcolor=COLORS["card"])
        style.configure("TSeparator", background=COLORS["line"])
        style.configure("TProgressbar", background=COLORS["teal"], troughcolor=COLORS["line"], borderwidth=0, thickness=5)
        style.configure("Dark.TLabelframe", background=COLORS["canvas"], foreground=COLORS["ink"], bordercolor=COLORS["line"])
        style.configure("Dark.TLabelframe.Label", background=COLORS["canvas"], foreground=COLORS["ink"], font=(system_family, 9, "bold"))

    def _build_shell(self) -> None:
        shell = ttk.Frame(self.root, style="App.TFrame", padding=(22, 18, 22, 18))
        shell.pack(fill="both", expand=True)

        top = ttk.Frame(shell, style="App.TFrame")
        top.pack(fill="x", pady=(0, 16))

        title_block = ttk.Frame(top, style="App.TFrame")
        title_block.pack(side="left", fill="x", expand=True)
        ttk.Label(title_block, text="Caderno de estudos", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_block, text="Sua trilha de programação e computação", style="Subtitle.TLabel").pack(anchor="w", pady=(3, 0))

        summary = ttk.Frame(top, style="App.TFrame", width=280)
        summary.pack(side="right", padx=(18, 0), anchor="center")
        summary.pack_propagate(False)
        ttk.Label(summary, textvariable=self.total_time_var, style="Summary.TLabel").pack(anchor="e", pady=(0, 4))
        ttk.Label(summary, textvariable=self.completed_var, style="Subtitle.TLabel").pack(anchor="e", pady=(0, 6))
        ttk.Progressbar(summary, maximum=len(self.subjects), variable=self.progress_var, style="TProgressbar").pack(fill="x")

        board = ttk.Frame(shell, style="App.TFrame")
        board.pack(fill="both", expand=True)
        for index, (status, heading) in enumerate(STATUS_COLUMNS):
            board.columnconfigure(index, weight=1, uniform="board-column")
            column = ScrollableColumn(board, status, heading)
            column.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 6, 0 if index == len(STATUS_COLUMNS) - 1 else 6))
            self.columns[status] = column
            self.column_counts[status] = column.count_var

    def _render_board(self) -> None:
        for column in self.columns.values():
            for child in column.cards_frame.winfo_children():
                child.destroy()

        grouped: dict[str, list[dict]] = {status: [] for status, _heading in STATUS_COLUMNS}
        for subject in self.subjects:
            status = self.statuses.get(subject["key"], "Pendente")
            if status not in grouped:
                status = "Pendente"
                self.statuses[subject["key"]] = status
            grouped[status].append(subject)

        for status, _heading in STATUS_COLUMNS:
            subjects = sorted(grouped[status], key=lambda item: item["priority"])
            column = self.columns[status]
            self.column_counts[status].set(str(len(subjects)))
            for subject in subjects:
                card = self._make_card(column.cards_frame, subject, status)
                card.pack(fill="x", padx=4, pady=(2, 8))

        resolved = sum(1 for subject in self.subjects if self.statuses.get(subject["key"]) == "Resolvido")
        self.completed_var.set(f"{resolved} de {len(self.subjects)} resolvidas")
        total_minutes = sum(self.session_minutes_by_subject.values())
        self.total_time_var.set(f"{_format_duration(total_minutes)} estudadas no total")
        self.progress_var.set(resolved)

    def _make_card(self, parent: tk.Misc, subject: dict, status: str) -> tk.Frame:
        card = tk.Frame(parent, background=COLORS["card"], highlightbackground=COLORS["line"], highlightthickness=1, borderwidth=0)
        stripe = tk.Frame(card, background=COLORS["amber"], width=4)
        stripe.pack(side="left", fill="y")

        body = ttk.Frame(card, style="Card.TFrame", padding=(9, 9, 9, 8))
        body.pack(side="left", fill="both", expand=True)

        header = ttk.Frame(body, style="Card.TFrame")
        header.pack(fill="x", pady=(0, 5))
        ttk.Label(header, text=f"{subject['priority']:02d}", style="Priority.TLabel").pack(side="left", anchor="n", padx=(0, 7))
        ttk.Label(header, text=subject["name"], style="CardTitle.TLabel", wraplength=205, justify="left").pack(side="left", fill="x", expand=True, anchor="w")

        self._recommendation(body, "Teoria", subject.get("theory", ""))
        self._recommendation(body, "Prática", subject.get("practice", ""))

        time_summary = self._card_time_summary(subject["key"])
        if time_summary:
            ttk.Label(body, text=time_summary, style="CardTime.TLabel", wraplength=305, justify="left").pack(anchor="w", pady=(5, 0))

        resources_count = len(subject.get("resources", []))
        books_count = len(subject.get("books", []))
        materials = ttk.Frame(body, style="Card.TFrame")
        materials.pack(fill="x", pady=(6, 4))
        summary = []
        if resources_count:
            summary.append(f"{resources_count} recursos")
        if books_count:
            summary.append(f"{books_count} livros")
        ttk.Label(materials, text=" · ".join(summary) or "Anotações e tempo de estudo", style="CardText.TLabel").pack(side="left", anchor="w")
        ttk.Button(
            materials,
            text="Abrir tema",
            style="Materials.TButton",
            command=lambda item=subject: self._show_subject_details(item),
        ).pack(side="right")

        status_row = ttk.Frame(body, style="Card.TFrame")
        status_row.pack(fill="x", pady=(6, 0))
        ttk.Label(status_row, text="Status", style="CardText.TLabel").pack(side="left")
        status_var = tk.StringVar(value=status)
        selector = ttk.Combobox(
            status_row,
            textvariable=status_var,
            values=EXPECTED_STATUSES,
            state="readonly",
            width=11,
            style="Board.TCombobox",
        )
        selector.pack(side="right")
        selector.bind(
            "<<ComboboxSelected>>",
            lambda _event, key=subject["key"], old=status, variable=status_var: self._change_status(key, old, variable.get()),
        )
        return card

    def _card_time_summary(self, subject_key: str) -> str:
        details = self.subject_details[subject_key]
        mode = details["time_mode"]
        if mode == "sessions":
            planned = details.get("planned_minutes")
            logged = self.session_minutes_by_subject.get(subject_key, 0)
            if planned is None:
                if logged:
                    return f"{_format_duration(logged)} estudadas · previsão não definida"
                return ""
            if logged > planned:
                return f"{_format_duration(logged)} estudadas · previsão ultrapassada"
            return f"{_format_duration(logged)} estudadas · faltam {_format_duration(planned - logged)}"
        if mode == "manual":
            remaining = details.get("manual_remaining_minutes")
            return f"Restam {_format_duration(remaining)}" if remaining is not None else ""
        target = details.get("target_date")
        if not target:
            return ""
        days = (date.fromisoformat(target) - date.today()).days
        if days > 0:
            return f"Concluir até {target} · faltam {days} dias"
        if days == 0:
            return f"Concluir até {target} · data de hoje"
        return f"Concluir até {target} · atraso de {abs(days)} dias"

    def _recommendation(self, parent: tk.Misc, label: str, value: str) -> None:
        if not value:
            return
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x", pady=(2, 0))
        ttk.Label(row, text=f"{label}:", style="CardText.TLabel", width=8, anchor="w").pack(side="left", anchor="n")
        ttk.Label(row, text=value, style="CardText.TLabel", wraplength=178, justify="left").pack(side="left", fill="x", expand=True, anchor="w")

    def _change_status(self, subject_key: str, old_status: str, new_status: str) -> None:
        if new_status == old_status:
            return
        try:
            save_status(subject_key, new_status)
        except (OSError, sqlite3.Error, ValueError) as error:
            self._render_board()
            _show_app_dialog(
                self.root,
                "Não foi possível salvar",
                f"O status não foi alterado porque o progresso não pôde ser salvo.\n\n{error}",
            )
            return
        self.statuses[subject_key] = new_status
        self._render_board()

    def _show_subject_details(self, subject: dict) -> None:
        subject_key = subject["key"]
        existing = self.detail_windows.get(subject_key)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Caderno — {subject['name']}")
        dialog.geometry("720x720")
        dialog.minsize(560, 520)
        dialog.configure(background=COLORS["canvas"])
        dialog.transient(self.root)
        self.detail_windows[subject_key] = dialog

        outer = ttk.Frame(dialog, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=subject["name"], style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text=f"Prioridade {subject['priority']:02d} · materiais, anotações e tempo",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 12))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        materials_tab = ttk.Frame(notebook, style="App.TFrame", padding=10)
        notes_tab = ttk.Frame(notebook, style="App.TFrame", padding=12)
        time_tab = ttk.Frame(notebook, style="App.TFrame", padding=12)
        notebook.add(materials_tab, text="Materiais")
        notebook.add(notes_tab, text="Anotações")
        notebook.add(time_tab, text="Tempo")

        self._build_materials_tab(materials_tab, subject)
        self._build_notes_tab(notes_tab, subject_key)
        self._build_time_tab(time_tab, subject_key)

        footer = ttk.Frame(outer, style="App.TFrame")
        footer.pack(fill="x", pady=(12, 0))
        ttk.Button(
            footer,
            text="Fechar",
            command=lambda key=subject_key, window=dialog: self._close_subject_window(key, window),
        ).pack(side="right")
        dialog.protocol("WM_DELETE_WINDOW", lambda: self._close_subject_window(subject_key, dialog))
        dialog.bind("<Escape>", lambda _event: self._close_subject_window(subject_key, dialog))
        dialog.grab_set()

    def _build_materials_tab(self, parent: ttk.Frame, subject: dict) -> None:
        text_frame = ttk.Frame(parent, style="App.TFrame")
        text_frame.pack(fill="both", expand=True)
        details = tk.Text(
            text_frame,
            wrap="word",
            background=COLORS["card"],
            foreground=COLORS["ink"],
            insertbackground=COLORS["teal"],
            selectbackground=COLORS["selection"],
            selectforeground=COLORS["ink"],
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=12,
            font=(tkfont.nametofont("TkDefaultFont").actual("family"), 10),
            spacing1=3,
            spacing3=5,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["teal"],
        )
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=details.yview, style="Vertical.TScrollbar")
        details.configure(yscrollcommand=scrollbar.set)
        details.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        details.tag_configure("section", font=(tkfont.nametofont("TkDefaultFont").actual("family"), 11, "bold"), foreground=COLORS["teal"], spacing1=10)
        details.tag_configure("title", font=(tkfont.nametofont("TkDefaultFont").actual("family"), 10, "bold"), foreground=COLORS["ink"])
        details.tag_configure("muted", foreground=COLORS["muted"])

        self._append_section(details, "Recomendações da trilha")
        details.insert("end", f"Teoria: {subject.get('theory', '—')}\n")
        details.insert("end", f"Prática: {subject.get('practice', '—')}\n")

        resources = subject.get("resources", [])
        if resources:
            self._append_section(details, f"Recursos da biblioteca ({len(resources)})")
            for resource in resources:
                details.insert("end", f"{resource.get('title', 'Recurso')}\n", "title")
                description = resource.get("description", "")
                kind = resource.get("type", "")
                metadata = " · ".join(part for part in (kind, resource.get("area", "")) if part)
                if description:
                    details.insert("end", f"{description}\n", "muted")
                if metadata:
                    details.insert("end", f"{metadata}\n", "muted")

        books = subject.get("books", [])
        if books:
            self._append_section(details, f"Livros ({len(books)})")
            for book in books:
                details.insert("end", f"{book.get('title', 'Livro')}\n", "title")
                if book.get("note"):
                    details.insert("end", f"{book['note']}\n", "muted")

        details.configure(state="disabled")

    def _build_notes_tab(self, parent: ttk.Frame, subject_key: str) -> None:
        ttk.Label(
            parent,
            text="Anotações livres deste tema. O texto é salvo automaticamente.",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        text_frame = ttk.Frame(parent, style="App.TFrame")
        text_frame.pack(fill="both", expand=True)
        editor = tk.Text(
            text_frame,
            wrap="word",
            undo=True,
            background=COLORS["card"],
            foreground=COLORS["ink"],
            insertbackground=COLORS["teal"],
            selectbackground=COLORS["selection"],
            selectforeground=COLORS["ink"],
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=12,
            font=(tkfont.nametofont("TkDefaultFont").actual("family"), 10),
            spacing1=3,
            spacing3=5,
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["teal"],
        )
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=editor.yview, style="Vertical.TScrollbar")
        editor.configure(yscrollcommand=scrollbar.set)
        editor.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        editor.insert("1.0", self.subject_details[subject_key].get("notes", ""))

        note_status = tk.StringVar(value="Salvo")
        status_row = ttk.Frame(parent, style="App.TFrame")
        status_row.pack(fill="x", pady=(8, 0))
        ttk.Label(status_row, textvariable=note_status, style="StatusLine.TLabel").pack(side="right")
        self.note_editors[subject_key] = {"widget": editor, "status": note_status, "after": None}
        editor.bind("<KeyRelease>", lambda _event, key=subject_key: self._queue_notes_save(key))
        editor.bind("<<Paste>>", lambda _event, key=subject_key: self.root.after_idle(self._queue_notes_save, key))
        editor.bind("<<Cut>>", lambda _event, key=subject_key: self.root.after_idle(self._queue_notes_save, key))

    def _queue_notes_save(self, subject_key: str) -> None:
        state = self.note_editors.get(subject_key)
        if state is None:
            return
        if state["after"] is not None:
            try:
                self.root.after_cancel(state["after"])
            except tk.TclError:
                pass
        state["status"].set("Salvando…")
        state["after"] = self.root.after(650, lambda key=subject_key: self._save_notes_now(key))

    def _save_notes_now(self, subject_key: str) -> bool:
        state = self.note_editors.get(subject_key)
        if state is None:
            return True
        if state["after"] is not None:
            try:
                self.root.after_cancel(state["after"])
            except tk.TclError:
                pass
            state["after"] = None
        notes = state["widget"].get("1.0", "end-1c")
        try:
            save_notes(subject_key, notes)
        except (OSError, sqlite3.Error, ValueError) as error:
            state["status"].set("Não foi possível salvar")
            state["last_error"] = str(error)
            return False
        self.subject_details[subject_key]["notes"] = notes
        state["status"].set("Salvo")
        state["last_error"] = ""
        return True

    def _close_subject_window(self, subject_key: str, dialog: tk.Toplevel) -> None:
        if not self._save_notes_now(subject_key):
            state = self.note_editors.get(subject_key, {})
            _show_app_dialog(
                dialog,
                "Anotação não salva",
                "Não foi possível salvar sua anotação. Corrija o problema e tente fechar novamente.\n\n"
                + state.get("last_error", ""),
            )
            return
        if dialog.winfo_exists():
            dialog.destroy()
        self.detail_windows.pop(subject_key, None)
        self.note_editors.pop(subject_key, None)
        self.time_tabs.pop(subject_key, None)

    def _build_time_tab(self, parent: ttk.Frame, subject_key: str) -> None:
        ttk.Label(parent, text="Escolha como quer acompanhar o tempo deste tema.", style="Hint.TLabel").pack(anchor="w", pady=(0, 8))
        mode_row = ttk.Frame(parent, style="App.TFrame")
        mode_row.pack(fill="x", pady=(0, 10))
        ttk.Label(mode_row, text="Modo", style="FormHeading.TLabel").pack(side="left", padx=(0, 10))
        mode_var = tk.StringVar(value=MODE_LABELS[self.subject_details[subject_key]["time_mode"]])
        selector = ttk.Combobox(
            mode_row,
            textvariable=mode_var,
            values=tuple(MODE_LABELS[mode] for mode in TIME_MODES),
            state="readonly",
            style="Board.TCombobox",
            width=34,
        )
        selector.pack(side="left", fill="x", expand=True)
        content = ttk.Frame(parent, style="App.TFrame")
        content.pack(fill="both", expand=True)
        self.time_tabs[subject_key] = {
            "mode_var": mode_var,
            "content": content,
            "fields": {},
            "summary": None,
            "tree": None,
            "subject": next(item for item in self.subjects if item["key"] == subject_key),
        }
        selector.bind("<<ComboboxSelected>>", lambda _event, key=subject_key: self._change_time_mode(key))
        self._render_time_mode(subject_key)

    def _render_time_mode(self, subject_key: str) -> None:
        state = self.time_tabs[subject_key]
        for child in state["content"].winfo_children():
            child.destroy()
        state["fields"] = {}
        state["summary"] = None
        state["tree"] = None
        mode = self.subject_details[subject_key]["time_mode"]
        if mode == "sessions":
            self._render_sessions_mode(subject_key)
        elif mode == "manual":
            self._render_manual_mode(subject_key)
        else:
            self._render_date_mode(subject_key)

    def _duration_fields(
        self,
        parent: tk.Misc,
        label: str,
        minutes: int | None,
    ) -> tuple[tk.StringVar, tk.StringVar]:
        section = ttk.Frame(parent, style="App.TFrame")
        section.pack(fill="x", pady=(0, 7))
        ttk.Label(section, text=label, style="FormHeading.TLabel").pack(anchor="w", pady=(0, 5))
        row = ttk.Frame(section, style="App.TFrame")
        row.pack(anchor="w")
        hours, remainder = divmod(minutes, 60) if minutes is not None else (None, None)
        hours_var = tk.StringVar(value="" if hours is None else str(hours))
        minutes_var = tk.StringVar(value="" if remainder is None else str(remainder))
        ttk.Entry(row, textvariable=hours_var, width=7).pack(side="left")
        ttk.Label(row, text="h", style="Hint.TLabel").pack(side="left", padx=(5, 12))
        ttk.Entry(row, textvariable=minutes_var, width=7).pack(side="left")
        ttk.Label(row, text="min", style="Hint.TLabel").pack(side="left", padx=(5, 0))
        return hours_var, minutes_var

    def _render_sessions_mode(self, subject_key: str) -> None:
        state = self.time_tabs[subject_key]
        details = self.subject_details[subject_key]
        planned_fields = self._duration_fields(
            state["content"],
            "Tempo total previsto",
            details.get("planned_minutes"),
        )
        state["fields"]["planned"] = planned_fields
        ttk.Button(
            state["content"],
            text="Salvar previsão",
            style="Primary.TButton",
            command=lambda key=subject_key: self._save_time_value(key),
        ).pack(anchor="w", pady=(0, 8))

        summary = tk.StringVar()
        ttk.Label(state["content"], textvariable=summary, style="Summary.TLabel").pack(anchor="w", pady=(0, 12))
        state["summary"] = summary

        ttk.Separator(state["content"], orient="horizontal").pack(fill="x", pady=(0, 12))
        ttk.Label(state["content"], text="Registrar uma sessão", style="FormHeading.TLabel").pack(anchor="w", pady=(0, 6))
        session_fields = self._duration_fields(state["content"], "Duração", None)
        state["fields"]["session"] = session_fields
        date_row = ttk.Frame(state["content"], style="App.TFrame")
        date_row.pack(fill="x", pady=(0, 8))
        ttk.Label(date_row, text="Data", style="Hint.TLabel").pack(side="left", padx=(0, 10))
        session_date = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(date_row, textvariable=session_date, width=14).pack(side="left")
        ttk.Label(date_row, text="AAAA-MM-DD", style="Hint.TLabel").pack(side="left", padx=(8, 0))
        state["fields"]["session_date"] = session_date
        ttk.Button(
            state["content"],
            text="Adicionar sessão",
            style="Primary.TButton",
            command=lambda key=subject_key: self._add_study_session(key),
        ).pack(anchor="w", pady=(0, 10))

        session_frame = ttk.Frame(state["content"], style="App.TFrame")
        session_frame.pack(fill="both", expand=True)
        session_frame.columnconfigure(0, weight=1)
        session_frame.rowconfigure(0, weight=1)
        tree = ttk.Treeview(
            session_frame,
            columns=("date", "duration"),
            show="headings",
            height=6,
            style="Dark.Treeview",
        )
        tree.heading("date", text="Data")
        tree.heading("duration", text="Duração")
        tree.column("date", width=130, anchor="w")
        tree.column("duration", width=130, anchor="w")
        scrollbar = ttk.Scrollbar(session_frame, orient="vertical", command=tree.yview, style="Vertical.TScrollbar")
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        state["tree"] = tree
        ttk.Button(
            state["content"],
            text="Remover sessão selecionada",
            command=lambda key=subject_key: self._delete_selected_session(key),
        ).pack(anchor="e", pady=(7, 0))
        self._refresh_sessions_tab(subject_key)

    def _render_manual_mode(self, subject_key: str) -> None:
        state = self.time_tabs[subject_key]
        fields = self._duration_fields(
            state["content"],
            "Tempo que falta",
            self.subject_details[subject_key].get("manual_remaining_minutes"),
        )
        state["fields"]["manual"] = fields
        ttk.Label(
            state["content"],
            text="Atualize esse valor conforme avançar no tema.",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(2, 8))
        ttk.Button(
            state["content"],
            text="Salvar tempo restante",
            style="Primary.TButton",
            command=lambda key=subject_key: self._save_time_value(key),
        ).pack(anchor="w")

    def _render_date_mode(self, subject_key: str) -> None:
        state = self.time_tabs[subject_key]
        ttk.Label(state["content"], text="Data prevista para concluir", style="FormHeading.TLabel").pack(anchor="w", pady=(0, 6))
        target_date = tk.StringVar(value=self.subject_details[subject_key].get("target_date") or "")
        state["fields"]["target_date"] = target_date
        row = ttk.Frame(state["content"], style="App.TFrame")
        row.pack(anchor="w")
        ttk.Entry(row, textvariable=target_date, width=16).pack(side="left")
        ttk.Label(row, text="AAAA-MM-DD", style="Hint.TLabel").pack(side="left", padx=(8, 0))
        state["summary"] = tk.StringVar()
        ttk.Label(state["content"], textvariable=state["summary"], style="Summary.TLabel").pack(anchor="w", pady=(10, 10))
        ttk.Button(
            state["content"],
            text="Salvar data",
            style="Primary.TButton",
            command=lambda key=subject_key: self._save_time_value(key),
        ).pack(anchor="w")
        self._update_date_summary(subject_key)

    def _parse_duration_fields(
        self,
        fields: tuple[tk.StringVar, tk.StringVar],
        label: str,
        *,
        allow_empty: bool,
    ) -> int | None:
        raw_hours, raw_minutes = (value.get().strip() for value in fields)
        if not raw_hours and not raw_minutes:
            return None if allow_empty else 0
        if raw_hours and not raw_hours.isdecimal():
            raise ValueError(f"As horas em {label.lower()} devem ser um número inteiro.")
        if raw_minutes and not raw_minutes.isdecimal():
            raise ValueError(f"Os minutos em {label.lower()} devem ser um número inteiro.")
        hours = int(raw_hours or "0")
        minutes = int(raw_minutes or "0")
        if minutes > 59:
            raise ValueError(f"Os minutos em {label.lower()} devem ficar entre 0 e 59.")
        return hours * 60 + minutes

    def _current_mode_value(self, subject_key: str) -> int | str | None:
        mode = self.subject_details[subject_key]["time_mode"]
        fields = self.time_tabs[subject_key]["fields"]
        if mode == "sessions":
            return self._parse_duration_fields(fields["planned"], "tempo previsto", allow_empty=True)
        if mode == "manual":
            return self._parse_duration_fields(fields["manual"], "tempo restante", allow_empty=True)
        raw = fields["target_date"].get().strip()
        return date.fromisoformat(raw).isoformat() if raw else None

    def _write_value_to_details(self, subject_key: str, mode: str, value: int | str | None) -> None:
        details = self.subject_details[subject_key]
        if mode == "sessions":
            details["planned_minutes"] = value
        elif mode == "manual":
            details["manual_remaining_minutes"] = value
        else:
            details["target_date"] = value

    def _save_active_time_value(self, subject_key: str) -> None:
        mode = self.subject_details[subject_key]["time_mode"]
        value = self._current_mode_value(subject_key)
        save_time_settings(subject_key, mode, value)
        self._write_value_to_details(subject_key, mode, value)

    def _save_time_value(self, subject_key: str) -> None:
        try:
            self._save_active_time_value(subject_key)
        except (OSError, sqlite3.Error, ValueError) as error:
            _show_app_dialog(
                self.detail_windows[subject_key],
                "Não foi possível salvar",
                f"Confira o valor informado e tente novamente.\n\n{error}",
            )
            return
        if self.subject_details[subject_key]["time_mode"] == "sessions":
            self._update_session_summary(subject_key)
        elif self.subject_details[subject_key]["time_mode"] == "date":
            self._update_date_summary(subject_key)
        self.session_minutes_by_subject.update(load_session_totals([subject_key]))
        self._render_board()

    def _change_time_mode(self, subject_key: str) -> None:
        state = self.time_tabs[subject_key]
        old_mode = self.subject_details[subject_key]["time_mode"]
        new_mode = MODE_VALUES.get(state["mode_var"].get(), old_mode)
        if new_mode == old_mode:
            return
        try:
            self._save_active_time_value(subject_key)
            details = self.subject_details[subject_key]
            if new_mode == "sessions":
                value = details.get("planned_minutes")
            elif new_mode == "manual":
                value = details.get("manual_remaining_minutes")
            else:
                value = details.get("target_date")
            save_time_settings(subject_key, new_mode, value)
        except (OSError, sqlite3.Error, ValueError) as error:
            state["mode_var"].set(MODE_LABELS[old_mode])
            _show_app_dialog(
                self.detail_windows[subject_key],
                "Modo não alterado",
                f"Confira o valor atual antes de trocar o modo.\n\n{error}",
            )
            return

        self.subject_details[subject_key]["time_mode"] = new_mode
        self._render_time_mode(subject_key)
        self._render_board()

    def _add_study_session(self, subject_key: str) -> None:
        fields = self.time_tabs[subject_key]["fields"]
        try:
            minutes = self._parse_duration_fields(fields["session"], "duração da sessão", allow_empty=False)
            if minutes is None or minutes <= 0:
                raise ValueError("Informe uma duração maior que zero.")
            studied_at = date.fromisoformat(fields["session_date"].get().strip()).isoformat()
            add_session(subject_key, minutes, studied_at)
        except (OSError, sqlite3.Error, ValueError) as error:
            _show_app_dialog(
                self.detail_windows[subject_key],
                "Sessão não adicionada",
                f"Confira duração e data.\n\n{error}",
            )
            return
        self.session_minutes_by_subject.update(load_session_totals([subject_key]))
        self._refresh_sessions_tab(subject_key)
        self._render_board()

    def _refresh_sessions_tab(self, subject_key: str) -> None:
        state = self.time_tabs[subject_key]
        tree = state.get("tree")
        if tree is None:
            return
        for item in tree.get_children():
            tree.delete(item)
        try:
            sessions = load_sessions(subject_key)
            self.session_minutes_by_subject.update(load_session_totals([subject_key]))
        except (OSError, sqlite3.Error) as error:
            _show_app_dialog(
                self.detail_windows[subject_key],
                "Não foi possível carregar as sessões",
                str(error),
            )
            sessions = []
        for session in sessions:
            tree.insert(
                "",
                "end",
                iid=str(session["session_id"]),
                values=(session["studied_at"], _format_duration(session["duration_minutes"])),
            )
        self._update_session_summary(subject_key)

    def _update_session_summary(self, subject_key: str) -> None:
        state = self.time_tabs[subject_key]
        summary = state.get("summary")
        if summary is None:
            return
        logged = self.session_minutes_by_subject.get(subject_key, 0)
        planned = self.subject_details[subject_key].get("planned_minutes")
        if planned is None:
            summary.set(f"Estudado: {_format_duration(logged)} · defina uma previsão para ver o restante.")
        elif logged > planned:
            summary.set(
                f"Estudado: {_format_duration(logged)} de {_format_duration(planned)} · "
                f"previsão ultrapassada em {_format_duration(logged - planned)}."
            )
        else:
            summary.set(
                f"Estudado: {_format_duration(logged)} de {_format_duration(planned)} · "
                f"faltam {_format_duration(planned - logged)}."
            )

    def _delete_selected_session(self, subject_key: str) -> None:
        tree = self.time_tabs[subject_key].get("tree")
        if tree is None or not tree.selection():
            _show_app_dialog(
                self.detail_windows[subject_key],
                "Selecione uma sessão",
                "Escolha uma sessão da lista para remover.",
            )
            return
        session_id = int(tree.selection()[0])
        if not _show_app_dialog(
            self.detail_windows[subject_key],
            "Remover sessão",
            "Quer remover a sessão selecionada? Essa ação não pode ser desfeita.",
            confirm=True,
            confirm_label="Remover",
        ):
            return
        try:
            delete_session(session_id)
            self.session_minutes_by_subject.update(load_session_totals([subject_key]))
        except (OSError, sqlite3.Error) as error:
            _show_app_dialog(
                self.detail_windows[subject_key],
                "Não foi possível remover",
                str(error),
            )
            return
        self._refresh_sessions_tab(subject_key)
        self._render_board()

    def _update_date_summary(self, subject_key: str) -> None:
        state = self.time_tabs[subject_key]
        summary = state.get("summary")
        if summary is None:
            return
        target = self.subject_details[subject_key].get("target_date")
        if not target:
            summary.set("Defina uma data para ver quantos dias faltam.")
            return
        days = (date.fromisoformat(target) - date.today()).days
        if days > 0:
            summary.set(f"Faltam {days} dias para a data escolhida.")
        elif days == 0:
            summary.set("A data escolhida é hoje.")
        else:
            summary.set(f"A data escolhida passou há {abs(days)} dias.")

    @staticmethod
    def _append_section(text: tk.Text, title: str) -> None:
        text.insert("end", f"\n{title}\n", "section")

    def _on_mousewheel(self, event: tk.Event) -> None:
        self._scroll_at_pointer(event.x_root, event.y_root, -1 if event.delta > 0 else 1)

    def _on_linux_mousewheel(self, event: tk.Event) -> None:
        self._scroll_at_pointer(event.x_root, event.y_root, -1 if event.num == 4 else 1)

    def _scroll_at_pointer(self, x: int, y: int, direction: int) -> None:
        for column in self.columns.values():
            if column.contains_pointer(x, y):
                column.canvas.yview_scroll(direction * 3, "units")
                break


def run() -> None:
    root = tk.Tk()
    root.configure(background=COLORS["canvas"])
    root.withdraw()
    try:
        subjects = load_catalog()
        initialize(subjects)
        statuses = load_statuses(subjects)
        subject_details = load_subject_details(subject["key"] for subject in subjects)
        session_minutes_by_subject = load_session_totals(subject["key"] for subject in subjects)
    except (CatalogError, OSError, sqlite3.Error, ValueError) as error:
        root.title("Caderno de estudos")
        root.geometry("500x220")
        root.deiconify()
        _show_app_dialog(
            root,
            "Caderno de estudos",
            f"O app não conseguiu carregar o catálogo ou o progresso local.\n\n{error}",
        )
        root.destroy()
        return

    StudyBoard(root, subjects, statuses, subject_details, session_minutes_by_subject)
    root.deiconify()
    root.mainloop()
