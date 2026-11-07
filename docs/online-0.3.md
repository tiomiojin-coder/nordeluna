# Online 0.3 / Android 1.10

## Apresentação local da batalha

A simulação continua usando a ordem canônica anfitrião/convidado nos dois clientes.
O convidado recebe uma cena adaptada: a visão local apresenta seu Pokémon no índice
visual 0 (embaixo, de costas, HP numérico) e o adversário no índice visual 1.
O adaptador converte índices de comandos, alvos, send-out, animações, barras e
substituições sem trocar as equipes reais, alterar RNG ou modificar o checksum.
Os callbacks de seleção de golpe e de posição na equipe mantêm seus próprios índices.

Os módulos mantidos em `game-plugins/Nordeluna Online` devem ser instalados na pasta
`Plugins/Nordeluna Online` do jogo antes de compilar. A versão dos dois clientes é
`0.3.0`, com `BUILD=nordeluna-online-2026-11-06-4`. O relay revisão 2 permanece compatível.

## Conexão e interrupções

Online oferece **Testar conexão**, com latência observada pelo cliente, protocolo,
revisão do servidor e versão local. A igualdade entre as versões/dados dos jogadores
é verificada pelo relay ao aceitar a entrada na sala; o teste de saúde isolado não
compara um jogador que ainda não entrou.

Falhas de rede interrompem a simulação; as rotinas normais de transição devolvem o
jogador ao mapa/menu e mostram um aviso, sem atribuir vitória por desconexão. Não há
retomada de uma batalha interrompida: é preciso criar outra sala.

## Trocas

Uma tela mostra os dois Pokémon com ícones, nome, espécie, nível, shiny, item e OT.
A reserva só começa após confirmar essa tela. O mecanismo de escrow anterior é mantido.

O comprovante inclui data, parceiro, enviado, recebido e status. É anexado **antes**
da gravação final, na mesma chamada `Game.save` que grava a entrega e remove o ticket.
Uma falha nessa gravação desfaz a entrega e o comprovante em memória e mantém a
recuperação pendente. A confirmação visual só aparece depois do save bem-sucedido.
São preservados até 50 comprovantes no save, acessíveis pelo menu Online.

Ao voltar a um mapa seguro, uma troca pendente oferece recuperação uma vez por
ticket/sessão. A entrada **Troca pendente - recuperar** continua acessível no menu.
O aviso não interrompe outro menu, mensagem, evento em execução ou batalha.

## Diagnóstico Android

O port registra exceções Java localmente e, no próximo início, consulta
`ApplicationExitInfo` em Android 11+. Android 12+ pode fornecer também um tombstone
binário de crash nativo. Esses registros dependem da disponibilidade mantida pelo
sistema; um trace pode não existir ou já ter sido sobrescrito.

Um aviso oferece exportar o relatório anterior ou deixar para depois. Nada é enviado
automaticamente. O ZIP inclui um histórico limitado de diagnósticos, o logcat e os
logs de eventos/online disponíveis, sem incluir saves ou banco de trocas.

Essa melhoria não prova a causa do crash anterior nem garante que ele esteja corrigido.
É necessário analisar o relatório do aparelho e validar uma partida real.

[Referência Android](https://developer.android.com/reference/android/app/ApplicationExitInfo).

## Verificação

`python scripts/test-online-runtime.py` inclui testes com os dados reais do jogo,
ambos os lados, os métodos originais dos menus e o layout real da Customizable Battle UI
com objetos de exibição simulados. Verifica front/back, nomes, HP, alvos, envio,
ausência de alteração na simulação, comprovantes atômicos, confirmação, liberação de
recursos gráficos, avisos de recuperação, protocolo e classificação de desconexão.

A compilação Android valida as integrações Java/API. Ainda é necessária validação
visual em aparelhos para animações de golpes/plugins específicos e diagnósticos nativos.
