# Online 0.5 — salas, chat e diagnóstico (alterações locais)

## Escopo

Esta etapa integra salas e chat ao canal atual do mapa. Não cria um mapa RPG Maker
novo nem sincroniza personagens caminhando. O mapa físico e avatares da praça
continuam sendo uma etapa separada. As fontes são mantidas em
`game-plugins/Nordeluna Online`, com os novos módulos `014_RoomService.rb` e
`015_ChatPanel.rb`. Nenhuma build, push ou publicação Discloud foi solicitada
para estas alterações.

## Salas e reconexão

**Online > Sala e chat**, ou a entrada de mesmo nome no menu de pausa, oferece a
sala pública `PRACA` e salas por código de oito caracteres. O código é uma chave
de agrupamento compartilhável, não um sistema de contas ou autorização de acesso.
Chat é separado por sala e build; os emotes continuam limitados também ao mapa.

Após uma falha breve, o cliente mantém sala e token de retomada e tenta reconectar
por até 60 segundos, com intervalos crescentes de 1, 2, 4, 8 e 12 segundos. O painel
mostra desconexão, tentativas e restauração. O servidor mantém a possibilidade de
retomar a identidade por 120 segundos. Sair explicitamente desativa as tentativas.
Chegar à tela de título abandona a sessão. Batalha/troca suspende o canal social e
tenta retornar à mesma sala ao encerrar; nenhuma batalha interrompida é retomada.

## Chat

O servidor revisão 4 atribui nick e horário às mensagens, sem confiar em campos
de nick/data fornecidos no envio. Cada mensagem tem um ID do cliente: reenviá-la
após uma resposta perdida não a duplica durante a retenção e retomada da sessão.
Uma identidade nova não reenvia automaticamente uma mensagem antiga já tentada;
o jogador recebe um aviso para conferir o histórico.

- Máximo de 120 caracteres por mensagem e intervalo de dois segundos.
- Até 80 mensagens em memória por sala; salas inativas são removidas após 30 min.
- Até 200 históricos de sala no servidor. Reiniciar o servidor limpa o chat.
- O novo epoch do servidor reinicia o cursor do cliente sem confundir IDs antigos.
- Mensagens não são gravadas no SQLite das trocas e não são incluídas no log HTTP.
- Tags e caracteres de controle são rejeitados; o painel usa texto simples.

O painel recolhido mostra conexão e a mensagem mais recente com nick/horário.
Tocar nele abre o histórico. As setas ou direcionais rolam as linhas; **Escrever**
usa a entrada de texto existente do jogo; **Recolher** ou Voltar fecha o histórico.
O horário é mostrado no fuso do aparelho. O mundo local fica pausado enquanto o
histórico está aberto, mas o canal de rede continua atualizando. O estado do menu
e os controles são restaurados ao fechar. Sprites e bitmaps são liberados ao sair.

## Diagnóstico

**Online > Diagnóstico online** ou a entrada direta no menu de pausa abre uma
única tela com versão/build do cliente, endereço/versão/revisão/protocolo do
servidor, última latência, sala, estado e último erro da sessão. **Testar** atualiza
a consulta; **Copiar** copia o resumo sem tokens, mensagens ou dados dos Pokémon.
Campos longos podem ser rolados. Último erro fica em RAM e não é apagado por uma
reconexão bem-sucedida; o relatório de crash/exportação anterior permanece separado.

## Integração e validação

Cliente `0.5.0`, build `nordeluna-online-2026-11-07-1`, relay revisão `4`/versão
`0.5.0`. Atualizar ambos os clientes e o servidor é necessário para usar chat.
As rotas anteriores de batalhas/trocas e o banco existente são preservados.

`python -m unittest discover -s scripts/tests` verifica isolamento de salas/builds,
nick/data autoritativos, repetição idempotente, retomada de identidade, saída
explícita, retenção, epoch e dois clientes HTTP reais. Também preserva as regressões
de escrow e empacotamento.

`python scripts/test-online-runtime.py` executa as fontes com Ruby/dados reais e
testes de reconexão, limite de tempo, confirmação/deduplicação, renderização do
painel/diagnóstico com objetos gráficos simulados, limpeza e restauração de input.
Os testes anteriores de Noctgeist, Mega e alvo real de duplas continuam incluídos.

Ainda é necessária validação física do toque, entrada de texto e layout no Android
e Windows. A integração usa as APIs de mouse e texto do mkxp-z; não foi testada
em um celular nesta etapa.
