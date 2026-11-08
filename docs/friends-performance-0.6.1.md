# Amigos e desempenho — atualização local 0.6.1

Implementado nos fontes e no `Data/PluginScripts.rxdata` do jogo local. Nenhum envio ao GitHub, build de APK ou deploy no Discloud foi executado nesta tarefa.

## Amigos e convites

Abra o menu de pausa do jogo → **Amigos e convites**. A primeira abertura nesta sessão registra sua presença social. A partir daí, ela é atualizada durante a exploração; entrar na praça reutiliza seu canal existente, sem criar uma segunda conexão concorrente.

- Adicione pelo nick online exato. O outro jogador precisa aceitar o pedido. É possível cancelar pedidos, recusar e remover amigos.
- A lista mostra **Disponível**, **Ocupado** ou **Offline**, além da compatibilidade entre as versões dos jogos. Uma mudança de nick preserva a amizade porque ela usa a identidade da conta.
- **Meu status** permite escolher disponível ou ocupado. Essa preferência fica salva no progresso. Batalhas e trocas marcam ocupado temporariamente, sem apagar a preferência manual.
- Selecione um amigo disponível para convidar para batalha ou troca. As regras, seleção de equipe/oferta e confirmações já existentes continuam sendo utilizadas.
- O convite expira em dois minutos. A sala fica reservada ao destinatário. Aceitar um convite abre o fluxo normal: não inicia uma batalha ou transfere um Pokémon automaticamente.
- Pedidos e convites recebidos aparecem como um contador no item do menu. O jogador decide quando abrir; a exploração não recebe janelas automáticas.
- Ao sair ou perder a conexão, o status fica offline após cerca de 35 segundos sem atualização. Não há presença em segundo plano com o jogo suspenso.
- Limites: 100 amigos, 30 pedidos enviados, 50 recebidos e até três novos convites por minuto. A lista depende da identidade do save; importar um save com outra identidade muda a conta usada.

O recurso exige **cliente 0.6.1 e servidor revisão 6**. O cliente apresenta uma mensagem clara se o servidor for anterior. O ZIP preparado em `build/discloud/friends-performance-0.6.1/Nordeluna-Online-Discloud.zip` contém a atualização aditiva das tabelas sociais. Ele não inclui nem substitui o banco do servidor. Não foi publicado.

Os IDs online continuam `plaza=39`, `coliseum=null`, `market=null`. Esta atualização não ativa os interiores antes de configurar cliente e servidor juntos.

## Desempenho

Menu de pausa do jogo → **Desempenho**. No Android, os mesmos controles também foram adicionados ao painel da engrenagem → **Desempenho**, para a próxima build do APK. Cada opção alterna entre **Normal**, **Reduzido** e **Desligado**, de maneira independente.

| Opção | Reduzido | Desligado |
| --- | --- | --- |
| Partículas ambientais | Um terço da quantidade, até seis por perfil | Remove partículas ambientais |
| Sombras projetadas | Mantém a sombra do jogador, remove as dos NPCs | Oculta as sombras projetadas |
| Efeitos decorativos | Névoa mais simples, até quatro brilhos ambientais, sem raios e detalhes extras, menos marcas no barro | Oculta esses efeitos e deixa de criar marcas no barro |

As opções afetam os efeitos dos plugins de atmosfera, iluminação e barro. Não desativam animações de golpes nem mudam as regras, encontros, Pokémon, som ambiente ou áudio dos passos.

As preferências ficam em `.nordeluna-performance.cfg` na pasta de execução do jogo. São locais ao aparelho; não viajam no save e não entram no pacote do jogo. A atualização do APK preserva esse arquivo. O painel e o jogo usam o mesmo formato, com atualização em até um segundo. Arquivos inválidos voltam ao padrão normal; falhas de gravação preservam a preferência anterior e mostram um aviso.

## Instalação e validação

Os cinco plugins recompilados são RE Visual Core, Light System, Atmosphere, Mud Terrain e Online. Os demais plugins, mapas, tilesets e metadados dos mapas foram preservados. Backup dos fontes anteriores: `.cache/friends-performance-install/20261108-015647`. O backup anterior do bundle fica em `Plugins/.backups/plugins-20261108-015744-224087` na pasta do jogo.

Patch local com os fontes completos dos cinco plugins e o bundle: `build/plugin-update/Nordeluna-Plugins-Local-patch.zip`. O patch não contém saves nem banco online.

Validações executadas:

- 62 testes Python, incluindo servidor, pedidos, persistência, permissões de convites, compatibilidade, expiração e preservação das trocas concluídas.
- Regressões Ruby de batalhas, trocas, áreas, mapas sociais, amigos, presença, parsing e liberação do transporte após falhas.
- 23 verificações dos métodos reais dos efeitos e das preferências, incluindo mudanças independentes, descarte de sprites e falha de gravação.
- 213 verificações de regressão dos plugins existentes.
- Painel Java com persistência, recarga das opções e erro de gravação; controles de toque; aplicação do patch em uma cópia limpa do motor. Apenas SideMenu e strings mudaram em relação ao patch Android anterior.
- Auditoria do jogo instalado: 38 plugins, 196 arquivos Ruby, nenhum erro de sintaxe/dependências, fontes online iguais ao bundle compilado.

Não houve teste de partida entre dois aparelhos nem medição de FPS em um Android real nesta tarefa. O APK novo ainda precisa ser gerado e o servidor atualizado para usar amigos em produção.
