@echo off
setlocal
cd /d "%~dp0"

where pyw >nul 2>nul
if not errorlevel 1 (
  start "" pyw -3 -m caderno_de_estudos
  exit /b 0
)

where pythonw >nul 2>nul
if not errorlevel 1 (
  start "" pythonw -m caderno_de_estudos
  exit /b 0
)

echo Python 3 com suporte a Tkinter nao foi encontrado.
echo Instale Python 3.11 ou mais recente e habilite Tcl/Tk.
pause
