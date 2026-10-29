# Caderno de Estudos — registro de estudo

## Intenção

Completar o app desktop offline para que o usuário acompanhe não só o status da matéria, mas também suas anotações e o tempo dedicado a cada tema.

## Objetivos

- Preservar o quadro de 14 matérias ordenadas pela prioridade já definida, com os status `Pendente`, `Fazendo` e `Resolvido`.
- Disponibilizar, ao abrir um tema, abas para materiais da biblioteca, anotações pessoais e tempo de estudo.
- Usar tema escuro em todo o app, pois o usuário não gosta da aparência clara.
- Guardar um texto de anotações independente para cada matéria, editável e persistido localmente.
- Permitir acompanhar o tempo por matéria em um de três modos: horas previstas com sessões registradas, horas restantes informadas manualmente ou data de conclusão.
- Mostrar os dados correspondentes ao modo de acompanhamento selecionado em cada matéria e somar o tempo estudado no resumo do quadro quando houver sessões.
- Manter todas as informações no banco SQLite local, sem navegador, Wi-Fi, contas ou novos pacotes de execução.
- Preservar status já registrados na atualização do banco.

## Não objetivos

- Calcular automaticamente uma data de calendário a partir de horas por semana. O app só mostra uma data final quando o usuário a informa no modo correspondente.
- Rodar um cronômetro em segundo plano.
- Controlar progresso individual de cada livro ou recurso.
- Adicionar sincronização em nuvem, lembretes, prazos, contas ou chamadas de rede.
- Permitir editar o catálogo de matérias e recursos.

## Restrições

- Continuar sendo um app desktop multiplataforma para Linux e Windows, executado offline.
- Continuar usando Python, Tkinter e SQLite da biblioteca padrão.
- Manter o tema escuro fixo em todas as janelas, diálogos, campos de edição e abas; não oferecer tema claro.
- Manter dados sob o diretório local de aplicação já usado em cada sistema.
- Tratar duração como minutos inteiros no armazenamento; a interface pode receber horas e minutos e apresentar os valores em formato legível.
- Uma estimativa não preenchida significa que o tempo restante é desconhecido, não zero.
- Cada matéria usa um único modo de acompanhamento de tempo por vez; ao trocar de modo, os dados anteriores ficam armazenados para não serem perdidos.
- O status da matéria continua sendo uma decisão manual e não muda automaticamente quando as horas estimadas forem atingidas.

## Abordagens consideradas

1. **Horas previstas mais sessões de estudo — recomendada.** O usuário define a duração planejada de cada tema e registra a duração real das sessões. O app calcula o acumulado e o restante. É a melhor leitura de “tempo de conclusão” sem presumir uma agenda semanal; exige manter sessões minimamente atualizadas.
2. **Horas restantes editadas manualmente.** O usuário altera diretamente um campo com o tempo que falta. É mais simples de preencher, mas não guarda o histórico nem calcula o restante a partir do tempo estudado.
3. **Data-alvo por tema.** Cada tema recebe uma data final. Ajuda a acompanhar prazos, mas não informa quantas horas faltam e depende de uma intenção de calendário que o usuário ainda não expressou.

**Proposta aprovada pelo usuário em 2026-10-29:** oferecer os três modos e permitir escolher um por matéria. O usuário pediu as três formas; a escolha por matéria evita mostrar horas calculadas, horas restantes manuais e data-alvo como se fossem uma única estimativa. Ao trocar o modo, valores dos modos inativos são preservados.

## Experiência proposta

- Cada card mantém a aparência e a prioridade atuais. Se houver estimativa de duração, o card também mostra algo compacto como `2h estudadas · faltam 5h`.
- O botão de detalhes abre uma janela do tema com as abas `Materiais`, `Anotações` e `Tempo`.
- `Anotações` contém uma área de texto livre e persistente exclusiva para aquele tema. As alterações são salvas localmente sem exigir um botão separado; a interface informa quando terminou de salvar.
- `Tempo` permite escolher um dos três modos por tema: (1) informar a duração total prevista e adicionar sessões pela duração e data (data preenchida com o dia atual); (2) informar manualmente quantas horas faltam; ou (3) definir uma data de conclusão.
- No modo de sessões, a lista mostra os registros mais recentes e o acumulado. Uma sessão lançada por engano pode ser removida com confirmação. O restante é `máximo(estimativa - acumulado, 0)`; se o acumulado superar a estimativa, o app sinaliza que ela foi ultrapassada.
- No modo manual, o usuário atualiza diretamente as horas restantes. No modo de data, o app mostra a data escolhida e quantos dias faltam ou de atraso, sem criar lembretes.
- Ao trocar o modo de um tema, os dados de outros modos são preservados, mas ficam ocultos enquanto não forem reativados. O card mostra somente o resumo do modo ativo.
- O resumo do quadro passa a informar o total de horas registrado em sessões, além da quantidade de temas resolvidos.
- Os nomes de livros e recursos continuam como texto; o app não abre links.

## Direção visual

- Aplicar tema escuro consistente ao quadro, cards, janelas de detalhes, abas, áreas de texto, campos e caixas de diálogo do app.
- Usar fundo grafite (`#171C1F`), superfícies de card (`#242B2E`), texto principal claro (`#E7ECEA`), texto secundário (`#A2B0AA`), contorno discreto (`#394447`), teal claro (`#63C6B3`) para progresso e âmbar (`#E2AE55`) para prioridade.
- Diferenciar os estados com superfícies escuras próprias e texto legível, preservando contraste e foco visível dos controles.
- Não incluir alternância claro/escuro: o tema escuro é a preferência informada pelo usuário.

## Persistência e compatibilidade

- Estender o esquema local com armazenamento de anotações por chave de matéria, modo de tempo selecionado, estimativa e restante manual em minutos, data-alvo e uma tabela de sessões com identificador, chave de matéria, duração em minutos e data/hora.
- A inicialização deve migrar bancos existentes sem apagar ou redefinir status. A migração precisa ser segura para inicializações repetidas.
- Sessões são registradas e removidas individualmente; o total acumulado é calculado a partir delas para evitar divergência entre histórico e resumo. O modo ativo é armazenado por matéria, enquanto dados dos outros modos permanecem preservados.
- O catálogo JSON continua sendo a fonte de matérias e materiais, e a planilha original não é necessária durante a execução.

## Decisões de interface que ficam para implementação

- Reutilizar a janela de detalhes já existente e substituir sua visualização única por uma interface com abas Tkinter.
- Usar salvamento local com pequeno atraso após digitação nas anotações, cancelando o salvamento pendente quando a janela fecha após garantir que o texto atual foi persistido.
- Exibir durações em horas e minutos e aceitar campos claros para estimativa e sessão; não depender de digitação em formato de relógio ambíguo.
- Manter a prioridade e os três status atuais sem mudança de semântica.

## Critérios de conclusão

- Cada tema abre suas próprias anotações e elas reaparecem depois de fechar e abrir o app.
- É possível escolher cada um dos três modos por matéria; o modo de horas previstas calcula corretamente o acumulado e o restante, o modo manual preserva as horas informadas e o modo de data mostra a diferença em dias.
- Trocar o modo mantém os dados anteriores e não altera o status da matéria.
- Temas sem estimativa não aparecem como se tivessem zero minutos restantes.
- Um banco da versão atual mantém todos os status após a migração e passa a aceitar os novos dados.
- A interface continua iniciando no Linux e Windows com Python/Tkinter, sem rede ou dependências Python adicionais.
