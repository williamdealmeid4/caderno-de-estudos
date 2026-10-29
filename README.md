# Caderno de Estudos

App de desktop para registrar o progresso nas matérias de programação e computação da planilha `Biblioteca_Estudos_Programacao_Computacao.xlsx`.

## Como funciona

- O quadro tem 14 matérias, na ordem de prioridade da aba **Essenciais**.
- Cada card pode ficar como **Pendente**, **Fazendo** ou **Resolvido**.
- Ao mudar o status, o card muda de coluna e o progresso é salvo automaticamente no computador.
- O app usa tema escuro.
- Cada card tem a ação **Abrir tema**, com abas de materiais, anotações e tempo.
- As anotações são próprias de cada matéria e são salvas automaticamente no computador.
- Na aba **Tempo**, cada matéria usa um dos modos: horas previstas com sessões registradas, horas restantes informadas manualmente ou data de conclusão. Ao trocar de modo, os valores anteriores são preservados.
- O modo de sessões registra a duração e a data de cada sessão, mostra o total estudado e calcula quanto falta da previsão. O quadro também soma as sessões registradas.
- O modo manual mostra o tempo restante informado. O modo de data mostra quantos dias faltam ou se a data passou.
- A aba de materiais mostra recursos e livros da planilha como texto. O app não abre sites.
- O app não tem conta, sincronização ou chamadas de rede. Depois de instalado, funciona sem Wi-Fi.

## Linux

Requer Python 3.11 ou mais recente, com Tkinter instalado. Neste projeto, não é preciso instalar pacotes Python adicionais.

1. Execute `./install_linux.sh`.
2. Abra **Caderno de Estudos** no menu de aplicativos.

Para abrir direto, execute `./launch_linux.sh`.

## Windows

Requer Python 3.11 ou mais recente, instalado com Tcl/Tk.

1. Dê duplo clique em `launch_windows.pyw` para abrir sem janela de terminal.
2. Se a associação de arquivos `.pyw` não estiver configurada, use `launch_windows.bat`.

## Onde os dados ficam salvos

- Linux: `$XDG_DATA_HOME/caderno-de-estudos/progress.sqlite3` ou `~/.local/share/caderno-de-estudos/progress.sqlite3`.
- Windows: `%APPDATA%\CadernoDeEstudos\progress.sqlite3`.

Status, anotações, previsões, datas-alvo e sessões ficam nesse banco SQLite local, separado do código. A primeira abertura da nova versão atualiza o banco sem apagar os status já registrados. Para levar os dados para outro computador ou sistema, feche o app e copie `progress.sqlite3` para a pasta de dados correspondente.

## Atualizar o catálogo a partir da planilha

O app lê um catálogo JSON incluído no projeto e não precisa abrir o arquivo `.xlsx` durante o uso. Para gerar novamente esse catálogo:

```bash
python3 tools/import_workbook.py "/caminho/para/Biblioteca_Estudos_Programacao_Computacao.xlsx"
```

O importador usa apenas a biblioteca padrão do Python.
