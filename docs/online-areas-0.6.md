Áreas sociais online — Nordeluna Online 0.6.0
===========================================

Implementação local, integrada ao canal HTTP, às salas, ao chat, às batalhas e
às trocas existentes. O servidor está na revisão 5. Nenhum mapa foi criado
e nenhum APK foi gerado nesta etapa.

Em 07/11/2026, o servidor existente no Discloud foi atualizado para 0.6.0/revisão 5.
O endpoint público confirmou a Praça 39 e os outros dois mapas pendentes.
Os 21 registros anteriores de salas foram confirmados por consulta `inspect`
somente de leitura, sem alterar timestamps ou usar tokens de sala. O backup
anterior está em `.cache/discloud-deploy/20261107-203817-981990/before-update.zip`.
O token da API foi informado em janela local e não foi salvo. Não houve push no GitHub.

Configuração atual dos mapas
----------------------------------

Atualização local: os mapas 39 (70×70), 40 e 41 e a nova chegada em X=34/Y=59
estão descritos em [social-maps.md](social-maps.md). A configuração abaixo
registra o estado publicado antes desse pacote local.

A Praça Central está configurada como **mapa 39**, entrada em **X=21, Y=19**,
direção 2 (baixo). O mapa salvo tem 45×50 tiles; o ponto foi conferido nos dados
do tileset e permite passagem. Coliseu e Mercado Estelar continuam `nil` e
desabilitados até seus IDs serem informados. A Praça pode funcionar sozinha;
nenhum mapa da campanha foi habilitado como substituto.

No jogo, configure `Plugins/Nordeluna Online/016_IdentityAndAreas.rb`:

- `PLAZA_MAP_ID`: ID existente da Praça Central.
- `COLISEUM_MAP_ID`: ID existente do Coliseu.
- `MARKET_MAP_ID`: ID existente do Mercado Estelar.
- `PLAZA_ENTRY`: coordenadas X/Y e direção 2/4/6/8 em um tile livre da Praça.

Os IDs preenchidos precisam ser diferentes. Mantenha a cópia mantida em `game-plugins/`
sincronizada e recompile os plugins após configurar. O servidor precisa dos
mesmos valores na variável `NORDELUNA_ONLINE_AREAS`, se ela estiver definida,
em JSON com exatamente as chaves `plaza`, `coliseum` e `market`. Configuração atual:

```json
{"plaza":39,"coliseum":null,"market":null}
```

O pacote do servidor já usa esses valores como padrão, dispensando a variável
quando ela não existe. Uma variável antiga prevalece sobre o padrão e precisa
ser ajustada na seção Variáveis do Discloud. Reinicie depois da alteração.
Não é necessário reconectar ao passar entre os três mapas: a sala/instância e
o token permanecem iguais. Os eventos de porta usam as transferências normais
do RPG Maker; o plugin autoriza somente os três destinos online no servidor.

O comando “Servidor” apenas verifica e salva o endereço. A sessão social é
aberta em **Online → Sala e chat**, ou no atalho de pausa “Sala e chat”.
Os fluxos de PvP e troca por código continuam disponíveis; testes de conexão
e pedidos de saúde não abrem uma presença nem teleportam o jogador.

Fluxo implementado
------------------

1. Verifica revisão e correspondência dos mapas entre cliente e servidor.
2. Obtém a identidade persistente, verifica/registra o nick e abre a sala existente.
3. Mostra a confirmação para entrar na Praça Central.
4. “Não” envia `map_leave`, elimina o estado local e mantém o jogador no mesmo tile.
5. “Sim” registra mapa/X/Y/direção da campanha e os estados de bicicleta/surf/mergulho.
6. Salva com o mecanismo do Essentials em arquivo temporário, verifica o conteúdo
   e publica o save por rename. Mantém uma cópia anterior `.online-return.bak`.
7. Confirma o ponto gravado antes de autorizar a transferência e fazer o fade.
8. Mantém esse ponto separado da posição dentro dos mapas sociais; transitar entre
   Praça, Coliseu e Mercado não substitui o retorno.
9. Desconectar encerra a presença, limpa sprites/chat e volta ao ponto original,
   incluindo direção e estado de veículo, salvando o retorno.

Queda detectada limpa os personagens remotos e solicita o retorno. A transferência
aguarda uma situação segura: não ocorre no meio de uma janela de mensagem,
menu, evento em execução ou batalha. Um erro de salvamento inicial cancela a
entrada e preserva o arquivo anterior. Se falhar o save de saída, o ponto de
recuperação permanece disponível, sem tentativas infinitas de teletransporte.

Carregar um save de sessão interrompida restaura o mapa da campanha **antes** de
`Game.load_map` inicializar a cena. Não tenta reaproveitar silenciosamente um
token do processo encerrado. O ponto só é descartado após reposicionar o jogador.
Se o mapa original foi removido pela atualização, a carga informa o erro em vez
de adivinhar um local ou sobrescrever o save. Iniciar um novo jogo limpa o estado
transitório do canal e não mantém a presença anterior sendo renovada.

Sessões que não podem enviar a saída por perda de rede/processo expiram no
servidor em 15 segundos. Menus e a pergunta de confirmação têm manutenção da
presença sem publicar a posição da campanha; sessões suspensas para PvP/troca
usam o mecanismo existente de retomada ao terminar.

Identidade e nicks
-----------------

O projeto não possuía contas persistentes: apenas tokens temporários por sala
e o ID do treinador no save. Foi adicionada uma identidade mínima por save,
sem tela de login, email ou segundo sistema de autenticação concorrente.
O ID do treinador e o nome do protagonista não são alterados.

A identidade contém ID aleatório e segredo, gravados localmente **antes** do
primeiro registro remoto. As credenciais são separadas por endereço de servidor;
trocar a configuração não envia o segredo da conta de outro servidor.
O servidor armazena somente o hash do segredo, o nick,
o nick normalizado, criação e alteração. O segredo não entra em perfis públicos,
chat, snapshots de presença ou diagnósticos.

O nick aceita 3–16 letras ASCII, números ou underscore. Espaços, caracteres
invisíveis/de controle, nomes vazios e nomes administrativos reservados são
rejeitados. A comparação usa casefold; a exibição preserva a capitalização
escolhida. Consulta de disponibilidade auxilia a UI, mas a garantia final é a
restrição UNIQUE e a operação atômica no SQLite, inclusive entre conexões distintas.

Saves antigos recebem a identidade na primeira utilização; seus IDs de treinador
e Pokémon permanecem intactos. Um nick antigo ocupado ou fora do novo formato
precisa ser escolhido novamente em “Meu nick”. As tabelas e os comprovantes
anteriores de batalha/troca não são reescritos pela migração. Reservas de trocas
continuam recuperáveis pelos tokens já existentes.

Cada jogador deve usar seu próprio save: copiar o save também copia a identidade.
O servidor mantém uma presença de mapa por conta. O banco do servidor precisa
permanecer em armazenamento persistente; no Discloud o arquivo atual é
`data/relay.sqlite3`. Preserve a pasta `data/` e seus backups ao atualizar a aplicação.
Apagar esse banco também apaga reservas de nick e os comprovantes de troca.

Personagens, nicks e interações
------------------------------

`019_GhostPlayers.rb` renderiza personagens remotos como sprites, nunca como
eventos, NPCs físicos ou entradas em `$game_map.events`. Não modifica `through`
do jogador local nem os métodos de passabilidade: paredes e obstáculos continuam
sendo tratados pelo próprio Essentials.

Sincroniza sprite de aparência, posição, direção e caminhada. Interpola passos
curtos e reposiciona diretamente saltos grandes. Personagens só aparecem quando
mapa, instância e versão do conteúdo coincidem. Se faltar a imagem remota no
cliente, usa a aparência local como alternativa; não baixa imagens da rede.

O nick fica centralizado com sombra; há também o nick local. Fonte, cores,
afastamento, distância máxima e exibição são constantes em `016_IdentityAndAreas.rb`.
Nomes sobrepostos recebem deslocamento limitado e transparência. Mudanças de
mapa, saída, desaparecimento de um peer e recuperação descartam os recursos.

O menu “Jogadores próximos” permite selecionar quem está até dois tiles de
distância, inclusive sobre o mesmo tile. Mostra ID/nick e conecta aos fluxos
**existentes** de criar sala para desafio ou troca, compartilhando o código como
antes. Não foi inventado um sistema de amizade ou de convites automáticos.

Rede e desempenho
-----------------

- Movimento limitado a quatro tentativas por segundo; posição parada envia
  somente manutenção a cada três segundos, salvo chat/emote pendente.
- Sequência crescente em cada atualização; servidor rejeita pacotes antigos e
  campos capazes de forjar identidade/nick/sala. Cliente ignora respostas de outro mapa.
- Nick e aparência são associados ao ID e à revisão do perfil; snapshots omitem
  metadados já conhecidos. Cada visual é reaproveitado até sair ou mudar aparência.
- No máximo 40 personagens por snapshot, priorizando os próximos; sprites distantes
  são ocultados. A lista no cliente acompanha integralmente os peers presentes.
- Uma única operação de transporte por vez. Pedidos de primeiro plano bloqueiam
  o início de novos polls enquanto drenam o pedido existente.
- Desenho, Input e Graphics permanecem na thread principal; o transporte continua
  usando as pontes existentes de Windows/Android.

Validação automatizada
----------------------

`python -m unittest discover -s scripts/tests` inclui registro persistente,
case-insensitive, nomes inválidos/reservados, concorrência com dois bancos,
posse da conta, três mapas, isolamento de instância, recusa/saída real, sequências,
cache de perfis, manutenção sem posição da campanha e preservação de recibos antigos.

`python scripts/test-online-runtime.py` mantém as regressões de combate/troca/chat
anteriores e carrega a integração nova para testar aceitar/recusar, save confirmado,
erro parcial de disco, ida e volta pelos três mapas, perda durante transporte,
recuperação antes da carga, manutenção em menus, redução de pacotes repetidos,
interpolação, nick e descarte em 20 ciclos de 40 personagens.

Esses testes usam o Ruby real e os dados de Pokémon do jogo, com substitutos de
mapa, disco, tela e rede para os cenários de transferência. Não equivalem a uma
partida real entre dois aparelhos. Os IDs do Coliseu e Mercado Estelar continuam pendentes.

Correção do interpretador de eventos
-----------------------------------

O log de teste real revelou chamadas a `$game_map.interpreter`, método que não
existe no Essentials 21.1. Os três pontos (mapa/emotes, troca pendente e retorno)
agora usam `pbMapInterpreterRunning?`, que consulta `$game_system.map_interpreter`.
O teste foi corrigido para carregar Game_Map, Game_System e os helpers reais;
o substituto de mapa não inventa mais um método `interpreter`. Verifica evento
parado/em execução, adiamento das recuperações e inicialização sem mapa/sistema.

A linha isolada “Game data was not compiled” vem do compilador quando
`mustCompile` é falso; não significa a mesma falha das exceções repetidas.

Correção do acesso ao transporte e validação de áreas
--------------------------------------------------

O teste de conexão agora preserva `areas` e `version` do servidor: antes, o
resultado filtrado descartava esses campos e causava um falso desacordo de IDs.
Há regressão que chama o método real, sem substituir o resultado desse teste.

No Windows, o helper `WindowsHttpBridge-2.exe` usa uma caixa postal com sufixo
`windows-v2-<PID>`. O marcador `status` fica estável durante sua execução:
substituí-lo a cada 200 ms concorria com `File.binread` e provocava EACCES.
Bloqueios transitórios de leitura são tolerados; bloqueios persistentes viram
mensagem de conexão, com prazo limitado. A caixa separada evita conflito com um
helper antigo ainda ativo. Feche e reabra o jogo depois de instalar a atualização.
Compile com `csc /target:winexe /optimize+ /out:WindowsHttpBridge-2.exe WindowsHttpBridge.cs`.
O teste de integração verifica que o status não é regravado durante as requisições.

Roteiro manual obrigatório após configurar os IDs
------------------------------------------------

1. Faça backup do save e do banco. Conecte no PC, aceite e confira o retorno gravado,
   a mensagem e o ponto de entrada na Praça. Repita escolhendo “Não”; confira que
   o servidor remove a presença e a posição não muda.
2. Entre pela Rota 4 em X=15/Y=22. Vá ao Coliseu, desconecte e confirme mapa, tile e
   direção. Repita passando pelo Mercado. Teste também vindo de bicicleta/surf.
3. Use dois saves distintos no PC/Android: ocupe o mesmo tile, atravesse o outro
   jogador e confirme que paredes/árvores continuam bloqueando ambos.
4. Confira os dois nicks, troca de aparência, caminhada, rolagem da câmera, troca
   de mapa e limpeza das imagens. Ajuste legibilidade nas resoluções reais.
5. Registre `Lunar`; outra conta deve falhar ao tentar `lunar`, inclusive com a
   primeira offline. Reinicie o servidor sem apagar o banco e repita.
6. Abra mochila, equipe e chat por mais de 15 segundos: a presença deve continuar.
   Entre em PvP/troca e confira retomada ou retorno seguro após uma falha.
7. Desligue a internet na Praça e durante uma transferência. Confira que as imagens
   somem e o retorno ocorre em situação segura, sem vitória automática por queda.
8. Salve numa área online, encerre o processo e carregue. Deve voltar à campanha,
   preservando Pokémon, itens, nick e eventual troca pendente.
9. Teste mudança de sala, portas com direção 0, F12, novo jogo e um destino inválido.
   Nenhum cenário deve substituir o ponto original por um mapa social.
10. Reúna vários testers nas mesmas e em diferentes instâncias. Meça FPS/latência
    e memória por uma sessão prolongada; o limite de snapshots não é uma medição
    de capacidade do plano de hospedagem.
