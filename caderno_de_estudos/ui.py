"""Tkinter interface for the offline study board."""

from __future__ import annotations

import sqlite3
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

from .catalog import CatalogError, EXPECTED_STATUSES, load_catalog
from .storage import initialize, load_statuses, save_status

COLORS = {
    "canvas": "#F3F6F4",
    "card": "#FFFFFF",
    "ink": "#223239",
    "muted": "#64736F",
    "teal": "#187F77",
    "amber": "#C99032",
    "line": "#DCE5E1",
    "pending": "#E9EFEC",
    "doing": "#F5EBD5",
    "resolved": "#DDEDE8",
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
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
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
    def __init__(self, root: tk.Tk, subjects: list[dict], statuses: dict[str, str]) -> None:
        self.root = root
        self.subjects = subjects
        self.statuses = statuses
        self.columns: dict[str, ScrollableColumn] = {}
        self.column_counts: dict[str, tk.StringVar] = {}
        self.completed_var = tk.StringVar()
        self.progress_var = tk.DoubleVar(value=0)

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
        style.configure("App.TFrame", background=COLORS["canvas"])
        style.configure("Column.TFrame", background=COLORS["canvas"])
        style.configure("ColumnHeading.TLabel", background=COLORS["canvas"], foreground=COLORS["ink"], font=(system_family, 10, "bold"))
        style.configure("CountPending.TLabel", background=COLORS["pending"], foreground=COLORS["ink"], font=(system_family, 9, "bold"))
        style.configure("CountDoing.TLabel", background=COLORS["doing"], foreground=COLORS["ink"], font=(system_family, 9, "bold"))
        style.configure("CountResolved.TLabel", background=COLORS["resolved"], foreground=COLORS["teal"], font=(system_family, 9, "bold"))
        style.configure("Title.TLabel", background=COLORS["canvas"], foreground=COLORS["ink"], font=(heading_family, 20, "bold"))
        style.configure("Subtitle.TLabel", background=COLORS["canvas"], foreground=COLORS["muted"], font=(system_family, 10))
        style.configure("Summary.TLabel", background=COLORS["canvas"], foreground=COLORS["teal"], font=(system_family, 10, "bold"))
        style.configure("Card.TFrame", background=COLORS["card"])
        style.configure("CardTitle.TLabel", background=COLORS["card"], foreground=COLORS["ink"], font=(system_family, 11, "bold"))
        style.configure("CardText.TLabel", background=COLORS["card"], foreground=COLORS["muted"], font=(system_family, 9))
        style.configure("Priority.TLabel", background=COLORS["amber"], foreground=COLORS["ink"], font=(system_family, 9, "bold"), padding=(6, 3))
        style.configure("Board.TCombobox", padding=(4, 3), font=(system_family, 9))
        style.map("Board.TCombobox", fieldbackground=[("readonly", COLORS["card"])], foreground=[("readonly", COLORS["ink"])])
        style.configure("Materials.TButton", background=COLORS["card"], foreground=COLORS["teal"], font=(system_family, 9, "bold"), borderwidth=0, padding=(2, 4))
        style.map("Materials.TButton", foreground=[("active", COLORS["ink"])])
        style.configure("TProgressbar", background=COLORS["teal"], troughcolor=COLORS["line"], borderwidth=0, thickness=5)

    def _build_shell(self) -> None:
        shell = ttk.Frame(self.root, style="App.TFrame", padding=(22, 18, 22, 18))
        shell.pack(fill="both", expand=True)

        top = ttk.Frame(shell, style="App.TFrame")
        top.pack(fill="x", pady=(0, 16))

        title_block = ttk.Frame(top, style="App.TFrame")
        title_block.pack(side="left", fill="x", expand=True)
        ttk.Label(title_block, text="Caderno de estudos", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_block, text="Sua trilha de programação e computação", style="Subtitle.TLabel").pack(anchor="w", pady=(3, 0))

        summary = ttk.Frame(top, style="App.TFrame", width=250)
        summary.pack(side="right", padx=(18, 0), anchor="center")
        summary.pack_propagate(False)
        ttk.Label(summary, textvariable=self.completed_var, style="Summary.TLabel").pack(anchor="e", pady=(3, 6))
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

        resources_count = len(subject.get("resources", []))
        books_count = len(subject.get("books", []))
        if resources_count or books_count:
            materials = ttk.Frame(body, style="Card.TFrame")
            materials.pack(fill="x", pady=(6, 4))
            summary = []
            if resources_count:
                summary.append(f"{resources_count} recursos")
            if books_count:
                summary.append(f"{books_count} livros")
            ttk.Label(materials, text=" · ".join(summary), style="CardText.TLabel").pack(side="left", anchor="w")
            ttk.Button(
                materials,
                text="Ver materiais",
                style="Materials.TButton",
                command=lambda item=subject: self._show_materials(item),
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
            messagebox.showerror(
                "Não foi possível salvar",
                f"O status não foi alterado porque o progresso não pôde ser salvo.\n\n{error}",
                parent=self.root,
            )
            return
        self.statuses[subject_key] = new_status
        self._render_board()

    def _show_materials(self, subject: dict) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Materiais — {subject['name']}")
        dialog.geometry("620x620")
        dialog.minsize(480, 400)
        dialog.configure(background=COLORS["canvas"])
        dialog.transient(self.root)

        outer = ttk.Frame(dialog, style="App.TFrame", padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=subject["name"], style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text=f"Prioridade {subject['priority']:02d} · materiais da sua biblioteca", style="Subtitle.TLabel").pack(anchor="w", pady=(3, 12))

        text_frame = ttk.Frame(outer, style="App.TFrame")
        text_frame.pack(fill="both", expand=True)
        details = tk.Text(
            text_frame,
            wrap="word",
            background=COLORS["card"],
            foreground=COLORS["ink"],
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=12,
            font=(tkfont.nametofont("TkDefaultFont").actual("family"), 10),
            spacing1=3,
            spacing3=5,
        )
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=details.yview)
        details.configure(yscrollcommand=scrollbar.set)
        details.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        details.tag_configure("section", font=(tkfont.nametofont("TkDefaultFont").actual("family"), 11, "bold"), foreground=COLORS["teal"], spacing1=10)
        details.tag_configure("title", font=(tkfont.nametofont("TkDefaultFont").actual("family"), 10, "bold"))
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
        ttk.Button(outer, text="Fechar", command=dialog.destroy).pack(anchor="e", pady=(12, 0))
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.grab_set()

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
    root.withdraw()
    try:
        subjects = load_catalog()
        initialize(subjects)
        statuses = load_statuses(subjects)
    except (CatalogError, OSError, sqlite3.Error) as error:
        messagebox.showerror("Caderno de estudos", f"O app não conseguiu carregar o catálogo ou o progresso local.\n\n{error}", parent=root)
        root.destroy()
        return

    root.deiconify()
    StudyBoard(root, subjects, statuses)
    root.mainloop()
