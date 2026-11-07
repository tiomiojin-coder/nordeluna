# Online 0.4.1 / Android 1.11

## Instabilidade de rede

No motor Android fixado em `17a5ec6`, `httpPostBodyInternal` chama
`formResponse`, que usa `rb_hash_new`, `rb_str_new` e outras APIs Ruby, dentro de
`drop_gvl_guard`. Essas APIs não podem ser usadas com o GVL liberado. Além disso,
o cliente antigo matava Ruby threads que ainda podiam estar em HTTP nativo.
Isso constitui um defeito concreto no caminho usado pelo online, mas ainda não
há log do aparelho que confirme a causa de todos os crashes relatados.

Referência: https://docs.ruby-lang.org/capi/en/master/d6/dfb/include_2ruby_2thread_8h.html

## Transporte Android

Android agora usa `OnlineBridge` em Java. Ruby publica um pedido de dados na
mesma pasta privada do jogo; um executor Java único realiza HTTP e devolve um
resultado atômico. Nenhuma requisição Android do plugin usa HTTPLite ou cria
Ruby threads de rede, incluindo emotes. O pacote nativo continua fixado: este
patch contorna seu binding HTTP inseguro, sem afirmar que corrigiu o motor inteiro.

- Uma requisição de cada vez; sem fila ilimitada ou retries automáticos.
- Connect timeout de 4 s, leitura de 5 s, watchdog total de 10 s e limite Ruby de 12 s.
- Até 256 KiB por pedido e 512 KiB por resposta; logs limitados a 128 KiB.
- TLS padrão da plataforma, sem desativar validação de certificados ou seguir redirects.
- Sessão nova a cada início: pedidos de uma execução anterior não são reenviados.
- Pausar o aplicativo cancela o pedido cooperativamente e aborta a sessão online;
  isso não representa derrota e não apaga um ticket de troca pendente.
- Somente o Java acessa a rede Android; Graphics/Input/JSON do jogo ficam na thread Ruby principal.

Desktop continua usando o binding de sua própria versão do runtime. A cancelamento
nunca mata uma thread nativa: o próximo pedido espera que ela termine. A garantia
de evitar o binding inseguro é específica para o port Android desta versão.

O relatório de erro inclui `online-transport.log` com status, duração e classe da
falha, sem URL, corpo, token ou dados de Pokémon. Crash nativo continua sendo
coletado pelo diagnóstico do Android quando disponível.

## Copiar código

Ao criar sala de PvP ou troca, o menu mostra **Copiar código**, **Aguardar jogador**
e **Cancelar sala**. O botão usa `Input.clipboard=` do SDL/mkxp-z e copia apenas os
oito caracteres públicos. Cancelar preserva as regras normais de encerramento e
escrow. Se o runtime não oferecer clipboard, a mensagem continua exibindo o código.

## Compatibilidade e validação

Os dois clientes devem usar o build `nordeluna-online-2026-11-06-6`. O servidor
revisão 3 continua compatível; este patch não altera seu protocolo ou banco.

`test_online_bridge.py` compila o Java real com JDK 11 e executa HTTP local real:
Unicode, isolamento entre sessões, cancelamento, redirects, limite de resposta,
pausa, reconexão e ausência de segredo no log. `test-online-runtime.py` executa
Ruby e dados reais do jogo, incluindo todas as regressões de batalha/troca. O
teste de mailbox Ruby usa arquivos simulados porque o embedding de teste não tem
uma pilha Ruby de I/O suportada; o teste Java usa arquivos reais.

Validação visual e de partidas prolongadas no Android ainda é necessária. Se
houver novo fechamento, exportar o relatório após reabrir é necessário para
investigar gráficos, plugins ou outras falhas além deste transporte.
