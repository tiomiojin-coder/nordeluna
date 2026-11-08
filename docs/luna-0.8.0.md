# Online 0.8.0 — Luna Coins, missões e matchmaking

Cliente instalado localmente, com backup, sem GitHub ou build de APK. Servidor 0.8.0 / revisão 9 publicado e verificado no Discloud, com banco preservado (23 salas, cinco contas). O resultado está em `.cache/discloud-deploy/luna-0.8.0-status.json`; backup anterior em `.cache/discloud-deploy/20261108-142342-697284/before-update.zip`.

## Interface e direcional

O menu usa uma arte de observatório lunar e uma moeda dourada com lua turquesa, criadas com ImageGen. Os botões e textos são desenhados separadamente; toda a navegação funciona por cima/baixo e confirmar/voltar, com toque e arrasto também disponíveis. As imagens são carregadas e reduzidas uma vez, com fallback caso faltem arquivos.

Chat: abra **Online → Chat da sala**. Cima/baixo rolam o histórico; esquerda/direita selecionam **Escrever**, **Reconectar** ou **Recolher**, com destaque dourado. Confirmar executa a opção selecionada. Voltar fecha. Diagnóstico usa o mesmo padrão para **Testar**, **Copiar** e **Voltar**.

Nicks: bitmap aumentado para 264×60, nome em uma linha de 30 px e estado em outra de 26 px, sobre fundo escuro translúcido. A posição considera a largura real do texto e as bordas da tela. A interface não precisa reduzir nem recortar os nicks permitidos de até 16 caracteres.

## Carteira e missões

**Online → Luna Coins e missões** reúne missões diárias, loja, comunidade, extrato e recuperação de compra. Luna Coins ficam na conta do servidor e não usam o dinheiro da campanha. Mudar o nick mantém a carteira.

| Missão diária | Recompensa |
| --- | ---: |
| Visita à central Luna Coins | 10 LC |
| Concluir uma batalha com ao menos dois turnos | 20 LC |
| Concluir três batalhas com ao menos dois turnos | 40 LC |
| Concluir uma troca | 15 LC |

As recompensas são resgatadas na lista de missões, uma vez por missão por conta por dia. O dia vira à meia-noite UTC−3. As duas missões de batalha são cumulativas; perder uma partida válida também conta.

Progresso de batalha exige dois participantes distintos, ao menos dois turnos com comandos de ambos e resultados canônicos concordantes enviados pelos dois clientes. Queda, desistência ou resultado divergente não dão progresso. O cliente guarda relatórios pendentes para tentar novamente ao abrir a central. As trocas só contam quando o servidor grava a confirmação dos dois.

O servidor verifica a sessão, os comandos e o consenso; ele não simula a batalha inteira. Isso é um sistema casual com limites diários, não uma solução absoluta contra clientes modificados ou múltiplas contas.

## Loja inicial

| Produto | Preço |
| --- | ---: |
| 5 Poké Balls | 25 LC |
| 3 Poções | 15 LC |
| Ovo de Aipom | 80 LC |
| Noctgeist nível 5 | 150 LC |
| Roupas | Em breve; sem cobrança |

O ovo é um Pokémon com passos de incubação reais; só registra a espécie como capturada depois da eclosão normal. A moeda e os preços são exclusivos do online; não existe conversão para o dinheiro da campanha.

Cada compra tem um ID gravado no save antes do pedido. O servidor debita e cria o recibo de presente na mesma transação; repetir o ID retorna o recibo sem cobrar outra vez. Se a resposta se perder, **Recuperar compra** consulta o pedido original. A entrega usa o sistema de presentes, com recuperação, validação de espaço e salvamento atômico. Roupas permanecem desativadas até a inclusão futura dos sprites e da lógica de equipamento.

## Matchmaking

**Online → Batalhas e trocas → Procurar batalha**. Escolha regras e equipe antes de entrar. O servidor combina duas contas diferentes com a mesma versão e regras; simples/duplas e quantidade de Pokémon vêm das regras existentes.

A fila é temporária, consultada a cada dois segundos, com expiração de buscas sem heartbeat. Voltar cancela. Quando encontra alguém, cria uma sala normal e usa a batalha já existente, com a mesma perspectiva local e cópias da equipe da campanha. Não é necessário digitar um código. A busca não tem ranking ou MMR nesta versão.

## Desafio comunitário

**Central Luna Coins → Desafio comunitário**: a praça completa uma meta inicial de **50 batalhas válidas**. Cada batalha conta uma vez, independentemente de qual dos dois relatórios chegou primeiro. Após atingir a meta, cada conta que contribuiu pode resgatar **100 LC**, uma vez.

O evento inicial é `praca-50-v1`, sem prazo nesta versão. A carteira, os recibos, as missões e o progresso comunitário persistem após reinícios. Não há consultas novas de missão/carteira por frame: a central busca quando aberta ou atualizada. Matchmaking reutiliza uma chave de compatibilidade calculada uma vez por entrada.

## Arquivos e validação

- Artes e prompts: `assets/online-v2/README.md`.
- Economia/fila no servidor: `server/economy.py`.
- Clientes: `025_LunaEconomy.rb` e `026_Matchmaking.rb`.
- Prévia com as artes: `build/chat-layout/online-menu.png`.
- Pacote do servidor: `build/discloud/luna-0.8.0/Nordeluna-Online-Discloud.zip`.
- Backup dos fontes/arquivos: `.cache/luna-0.8-backups/20261108-142402`.
- Backup anterior do bundle: `Plugins/.backups/plugins-20261108-142403-105200` na pasta do jogo.

81 testes Python passaram. Regressões Ruby verificaram os métodos reais do cliente, navegação do chat sem mouse, nick longo, ovo real, compra com resposta perdida, ausência de segunda cobrança, bloqueio de roupas indisponíveis, handoff da busca para batalha e cancelamento. Auditoria: 38 plugins, 201 arquivos Ruby, nenhum erro de sintaxe/dependências. Mapas, tilesets e metadados foram preservados. Não houve teste entre dois aparelhos físicos com esta versão.

O celular precisa de um novo APK para receber as artes, menus e novos serviços. Atualizar somente o Discloud não muda o APK instalado. Até ambos atualizarem, partidas entre clientes sem suporte a relatórios não concedem progresso de missão.
