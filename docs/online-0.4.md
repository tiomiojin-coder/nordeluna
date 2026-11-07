# Online 0.4 — Android 1.10

## Nick

Online > Meu nick permite definir ou trocar um nome de até 24 caracteres. A
confirmação avisa que o progresso atual será salvo. O campo fica no save, separado
do nome do protagonista e do treinador original dos Pokémon. Se Game.save falhar,
o nick anterior é restaurado. Salas, PvP, trocas e emotes usam o nick online.
Comprovantes antigos preservam o nome que o parceiro usava na transação.

## Regras de sala

O anfitrião escolhe nível atual, 25, 50 ou 100; equipe exata de 1 a 6 Pokémon;
permissão de lendários, míticos e Ultra Beasts; e formato simples ou duplo. Duplas
exigem no mínimo dois Pokémon. A classificação usa as flags PBS da espécie/forma.
Espécies personalizadas precisam dessas flags para serem classificadas como lendárias.

O convidado consulta as regras antes de selecionar sua equipe e confirma aceitá-las.
O servidor conserva as regras do anfitrião e valida o tamanho das duas equipes.
Ambos os clientes validam espécies/restrições ao decodificar as equipes; o relay
não possui os dados PBS e isso não constitui um sistema anticheat.

Níveis e cura são aplicados exclusivamente às cópias de batalha. Na dupla, cada
jogador controla dois slots, envia alvos e comandos selados e sincroniza
substituições, desmaios, Mega Evolução e resultado na ordem canônica. O adaptador
visual mantém os dois Pokémon locais na parte de baixo.

## Emotes

Menu de pausa > Emotes online, ou Online > Emotes no mapa. É preciso entrar no
canal voluntariamente. Acenar, comemorar e chamar para batalha produzem balões
com o nick, visíveis para jogadores do mesmo mapa, servidor e build compatível.
“Chamar para batalha” é um emote social: o PvP ainda começa pelas salas com código.
Não há sincronização de personagens caminhando, chat livre ou início automático
de batalha nesta implementação.

O cliente consulta o mapa em segundo plano, sem chamadas Graphics/Input no worker.
Balões duram quatro segundos; identificadores de sequência impedem repetição em
cada consulta. O intervalo mínimo é de três segundos, também imposto no servidor.
Presença expira após 15 segundos sem atualização e não é persistida. Pausas longas,
batalhas ou perda de rede podem exigir entrar novamente no canal. Balões são
ocultados em menus/batalhas, descartados ao mudar de mapa e liberam bitmaps/sprites.

## Integração e entrega

Cliente 0.4.0, build `nordeluna-online-2026-11-06-5`; relay revisão 3. O protocolo
continua 1 e os formatos de sala antigos continuam aceitos pelo relay. Clientes
de builds diferentes não entram na mesma sala nem recebem emotes entre si.

O servidor Discloud precisa ser atualizado **posteriormente**, preservando o banco
SQLite e seus arquivos WAL/SHM. O pacote de servidor é gerado separadamente por
`scripts/package-discloud.py`; publicar o APK não atualiza o Discloud. As fontes
novas são mantidas em `game-plugins/Nordeluna Online` e na pasta do jogo; o bundle
compilado deve ser atualizado por `scripts/compile-online-plugin.py --install`
antes de gerar o APK pelo atualizador.

## Testes

`python scripts/test-online-runtime.py`: Ruby do jogo e dados reais de Essentials/
Gen9; regressões anteriores; nick persistente e rollback; restrições; batalha
dupla executada simultaneamente nos dois clientes, alvos, desmaios, substituições,
golpes em área, PP esgotado/Struggle e Mega Evolução dos dois treinadores;
emotes com transporte assíncrono e renderização simulada, intervalo e descarte.

`python -m unittest discover -s scripts/tests`: regras inválidas, persistência,
inspeção sem credenciais, tamanho das equipes, dois clientes HTTP com emotes,
isolamento por mapa/build, cooldown, expiração e regressões de trocas/empacotamento.

Ainda é necessária validação visual em Android e PC, especialmente animações e
combinações de golpes/abilities dos plugins instalados. A compilação no GitHub
valida a integração Android, mas não substitui testes de uma partida nos aparelhos.
