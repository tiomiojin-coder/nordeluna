# Loja visual, favoritos e emblemas — Online 0.8.1

Cliente instalado no jogo local, com backup. Nenhum envio ao GitHub ou build de APK. A publicação do servidor revisão 10 é acompanhada em `.cache/discloud-deploy/shop-0.8.1-status.json`.

## Prévia da compra

Em **Online → Luna Coins e missões → Loja lunar**, selecionar um produto abre um painel com:

- Sprite de frente do Pokémon, imagem de ovo ou ícone real do item, conforme o prêmio.
- Preço em Luna Coins, saldo atual e saldo que sobrará. Sem moedas suficientes, mostra quanto falta e não permite confirmar a compra.
- Botões **Comprar**, **Favoritar/Desfavoritar** e **Voltar**.

Esquerda/direita selecionam o botão; confirmar executa; voltar fecha. Cima/baixo alternam os prêmios se o produto tiver vários componentes. Toque continua disponível. Os sprites usam os carregadores nativos do Essentials, respeitando forma e shiny; a prévia não gera Pokémon, não muda a equipe, não reserva prêmio e não envia pedido de compra. Todos os sprites/bitmaps/viewports temporários são liberados ao fechar.

Os produtos ainda indisponíveis, como roupas, mostram **Em breve**, podem ser favoritados e não têm compra habilitada. A imagem tem fallback caso falte algum arquivo.

As compras continuam usando o ID persistido e o recibo recuperável da versão 0.8.0. O servidor confere o saldo e o preço novamente ao comprar. A loja mostra o saldo consultado ao abrir e atualiza após compra/recuperação; não cria polling de carteira por frame.

## Favoritos

Produtos marcados recebem `[F]` e aparecem primeiro entre os disponíveis. **Ver favoritos** filtra a lista; **Mostrar todos** retorna ao catálogo completo. A lista informa `faltam X LC` quando o saldo não basta.

Favoritos ficam no save, separados por endereço de servidor. A preferência acompanha exportações desse save. Marcar ou desmarcar exige salvamento; uma falha restaura a seleção anterior. Produtos indisponíveis ficam depois dos disponíveis, inclusive quando favoritos.

## Emblemas no nick

**Online → Meu perfil e status → Emblemas cosméticos** permite selecionar uma conquista desbloqueada ou retirar o próprio emblema:

| Emblema | Desbloqueio |
| --- | --- |
| Participante lunar | Contribuir com uma batalha válida para o evento da praça |
| Praça unida | Ter contribuído para o evento que alcançou 50 batalhas |

O emblema é uma pequena estrela colorida junto do nick. Não muda atributos, regras ou saldo. Sem escolha explícita, o servidor seleciona automaticamente a maior conquista disponível. A escolha **Nenhum emblema no meu nick** retira a exibição para os outros jogadores sem apagar as conquistas.

**Ocultar emblemas nesta tela** esconde todos os emblemas localmente; pode ser revertido por **Mostrar emblemas nesta tela**. Essa preferência é salva no progresso e não altera a escolha pública dos outros jogadores. O texto do nick continua inteiro, e a área de desenho reserva espaço para o símbolo.

Conquistas e seleção pública são verificadas no servidor. O cliente não pode enviar um emblema inventado pelo pacote de movimento. A seleção persiste no banco e a preferência de visibilidade fica no save.

Para manter o servidor leve, a consulta de emblemas é cacheada por conta por até 60 segundos, com invalidação ao conquistar/selecionar e ao atingir a meta global. Pacotes de mapa só acrescentam o ID do símbolo. Trocar emblema não invalida o cache do gráfico do personagem nem faz uma consulta de banco por frame.

## Arquivos e verificações

- Cliente: `027_ShopPreviewAndBadges.rb` e integração nos menus/nicks.
- Servidor: `server/economy.py`, tabela aditiva `cosmetic_preferences`.
- Prévia renderizada com fonte aproximada e sprite real: `build/chat-layout/shop-preview.png`.
- Backup dos fontes: `.cache/shop-0.8.1-backups/20261108-152333`.
- Backup do bundle: `Plugins/.backups/plugins-20261108-152334-016225` na pasta do jogo.
- Pacote do servidor: `build/discloud/shop-0.8.1/Nordeluna-Online-Discloud.zip`.

85 testes Python passaram. As regressões Ruby exercitam os métodos reais da prévia, parâmetros de sprite de item/ovo/Fakemon, navegação pelo direcional, bloqueio por saldo, favoritamento e rollback de save, ausência de pedidos de compra ao visualizar/favoritar, descarte de recursos e nick longo com emblema. O servidor foi testado contra emblema não conquistado, seleção/remoção persistente, atualização sem recarregar o sprite e 100 leituras de cache sem SQL extra. Auditoria: 38 plugins, 202 arquivos Ruby, nenhum erro de sintaxe/dependências. Mapas e metadados foram preservados.

No celular, os novos painéis e os símbolos exigem o próximo APK. Não houve teste entre dois aparelhos físicos nesta tarefa.
