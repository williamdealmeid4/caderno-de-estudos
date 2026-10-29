#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DATA_HOME="${XDG_DATA_HOME:-${HOME:?}/.local/share}"
APPLICATIONS_DIR="$DATA_HOME/applications"
DESKTOP_FILE="$APPLICATIONS_DIR/caderno-de-estudos.desktop"

mkdir -p "$APPLICATIONS_DIR"
chmod +x "$APP_DIR/launch_linux.sh"

python3 - "$APP_DIR" "$DESKTOP_FILE" <<'PY'
from pathlib import Path
import sys

app_dir = Path(sys.argv[1])
desktop_file = Path(sys.argv[2])

def quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

desktop_file.write_text(
    "\n".join((
        "[Desktop Entry]",
        "Type=Application",
        "Name=Caderno de Estudos",
        "Comment=Registre o progresso da sua trilha de estudos",
        f"Exec={quote(str(app_dir / 'launch_linux.sh'))}",
        f"Path={quote(str(app_dir))}",
        "Terminal=false",
        "StartupNotify=true",
        "Categories=Education;Office;",
        "",
    )),
    encoding="utf-8",
)
desktop_file.chmod(0o755)
print(f"Atalho criado em {desktop_file}")
PY

printf '%s\n' "Pronto. Procure por 'Caderno de Estudos' no menu de aplicativos."
