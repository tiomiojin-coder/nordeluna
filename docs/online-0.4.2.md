# Online 0.4.2 / Android 1.12

## Duplas

O seletor real do Essentials devolve o índice do próprio usuário como marcador
visual de vários golpes automáticos, em área e de suporte. O validador do online
tratava esse marcador como um alvo único escolhido e interrompia a batalha com
“Alvo indisponível”. Agora esses alvos são normalizados para -1 e o motor resolve
os destinatários. Alvos únicos continuam sendo validados, incluindo lado e estado.

Os testes executam `pbChooseTarget`, `pbFirstTarget` e `pbCreateTargetTexts` reais,
incluindo a conversão visual do convidado, para Reflect, Surf, Roost, Uproar e Tackle.

## Equipe e Mega

Uma equipe de seis contendo Noctgeist passa pela codificação, decodificação e
batalha determinística dos dois lados. Noctgeist não possui flag de lendário nos
dados atuais. Não foi comprovado que a espécie causava o fechamento relatado.
O preflight identifica falhas por Pokémon antes de conectar e permite confirmar
a equipe inteira quando a quantidade corresponde à regra.

Uma escolha explícita oferece Mega antes do golpe quando a forma/pedra permitem.
Uma Mega já selecionada continua disponível ao menu para mostrar o estado e
permitir alterná-lo, sem liberar uma segunda Mega na mesma equipe. Os dois lados
têm o mesmo acesso virtual ao requisito de anel; a forma e demais restrições do
Pokémon continuam necessárias.

## Android

O marcador de estado agora é publicado sem truncar o arquivo visível. O cliente
tolera sua inicialização e não compara relógio Ruby com mtime Java para considerar
o transporte pronto. O watchdog da requisição continua limitando o tempo de espera.
Isso corrige a mensagem indevida de “Atualize o APK” apresentada em uma captura.

## Windows

O Windows também deixa de usar HTTPLite no online. O helper `WindowsHttpBridge.exe`
é um executável .NET Framework com subsistema Windows, sem janela de console.
Ele é iniciado por vetor de argumentos, limita tempo/tamanho das requisições,
valida TLS e não segue redirects. Cada processo do jogo tem sua própria mailbox.
O helper encerra com o processo pai e tenta registrar seu código de saída no log.

O patch Windows inclui o helper além dos scripts e do bundle. Para recompilá-lo,
na pasta `game-plugins/Nordeluna Online/bridge`, usar o csc do .NET Framework:
`csc /target:winexe /optimize+ /out:WindowsHttpBridge.exe WindowsHttpBridge.cs`.
O teste Windows compila a fonte e valida o subsistema PE, HTTP real com seis
Pokémon/Unicode, cancelamento, sessão antiga e encerramento pelo processo pai.
No Linux, esse teste é pulado; o teste Java/Android continua sendo executado.

O novo helper reduz o risco do caminho HTTP nativo dentro da VM. Ainda não há
relatório que identifique a causa de um possível fechamento offline do Game.exe.
Fechamento involuntário não é comportamento normal; é necessário investigar logs
e o código de saída se ele persistir.

## Emotes

Escolher um emote conecta o canal se necessário, fecha os menus e volta ao mapa
para enviar a fila. Os balões têm ícones desenhados, sem depender de fonte emoji.
Canal expirado tenta uma nova entrada e preserva o emote pendente. Sair do canal
explicitamente cancela a reconexão. Ambos devem estar no mesmo mapa, servidor e
build, com o canal conectado; o recurso não sincroniza personagens caminhando.

## Compatibilidade

Build `nordeluna-online-2026-11-06-7`; os dois jogadores precisam atualizar. Relay
revisão 3 continua compatível e não exige novo deploy. Nenhum save ou banco foi
apagado. Validação visual e partidas prolongadas em aparelhos ainda são necessárias.
