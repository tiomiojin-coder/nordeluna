# Presentes e eficiência — Online 0.7.0 / revisão 8

O cliente foi instalado e recompilado no jogo local, com backup. O servidor foi publicado e verificado no Discloud: versão 0.7.0, revisão 8, recursos de presentes ativos e banco preservado (23 salas, cinco contas). Nenhuma build de APK ou envio ao GitHub foi executado. O resultado da publicação fica em `.cache/discloud-deploy/gifts-0.7.0-status.json`; o backup anterior está em `.cache/discloud-deploy/20261108-133134-367227/before-update.zip`.

## Jogadores

Menu de pausa → **Online → Presentes**:

1. **Resgatar código** aceita digitação/colagem e apresenta o conteúdo antes de confirmar.
2. **Recuperar presente** continua uma entrega interrompida ou confirma uma entrega já gravada.
3. **Histórico de resgates** mostra reservado, entrega iniciada ou recebido.

Recompensas suportadas: itens com quantidade, dinheiro e Pokémon com espécie/Fakemon, nível, forma, shiny, item segurado e até quatro golpes definidos. Golpes vazios usam os golpes normais do nível/forma. O treinador original dos Pokémon de presente é Nordeluna. A espécie recebida é registrada na Pokédex quando a entrega é salva.

Equipe cheia usa os boxes. Se não houver espaço na mochila/boxes ou se o dinheiro ultrapassar o limite, nenhum componente do pacote é entregue parcialmente. O presente continua reservado; o jogador libera espaço e recupera depois.

O recurso exige o **cliente 0.7.0 e servidor revisão 8**. Após instalar esse cliente, novos códigos são cadastrados no servidor sem outro APK. Um APK antigo não ganha o menu somente pela atualização do Discloud.

## Administrador no Windows

Abra **Presentes Nordeluna.cmd**, na pasta do port. O gerenciador:

- Lê o PBS local para oferecer espécies, itens e golpes, incluindo Noctgeist e outros Fakemon.
- Permite definir código, título, validade, limite total e até dez recompensas no pacote.
- Interpreta a validade como `AAAA-MM-DD HH:MM`, no fuso UTC−3. Campos de validade/limite vazios deixam o código sem esse limite.
- Publica com o botão **Publicar presente**, lista os publicados e permite encerrar novos resgates.
- Usa o token Discloud somente no campo mascarado da janela; não o grava em arquivos, APK, servidor público ou argumentos de processo.

Nenhum código de produção foi criado automaticamente. Os códigos de teste só existem nos bancos temporários dos testes. O gerenciador atua na aplicação Nordeluna Online, sem alterar outras aplicações da conta Discloud. A operação administrativa usa o console autenticado da hospedagem; não existe uma rota administrativa aberta em `/api`.

Presentes publicados são imutáveis: para mudar o conteúdo, crie outro código. Encerrar ou expirar um código impede novos resgates e preserva o direito aos que já foram reservados. Uma reserva já conta no limite total, inclusive enquanto aguarda espaço no aparelho.

## Entrega recuperável

A chave única `(conta, presente)` no servidor impede um segundo resgate pelo mesmo ID online. Mudar o nick mantém esse ID. Isso não é uma restrição por aparelho ou pessoa; um novo save com outra identidade é outra conta.

O fluxo é reservado → entrega iniciada → recebido:

1. O servidor reserva um recibo único e uma cópia imutável das recompensas.
2. O cliente gera os Pokémon uma vez e grava o plano pendente antes de entregar.
3. O servidor grava a autorização de entrega.
4. O cliente entrega todos os componentes e grava o prêmio e o recibo juntos, usando o gravador atômico com backup.
5. Só então confirma a entrega no servidor. Se a resposta se perder, repete apenas a confirmação.

Falhas de salvamento restauram equipe, mochila, dinheiro, boxes e Pokédex em memória. Um recibo já iniciado sem seu plano local não pode ser reiniciado por um save antigo: é necessário usar o save original que tem o plano/recibo. A recuperação cobre fechamentos durante o processo, não a exclusão ou restauração arbitrária de saves antigos.

Não envie o código a outros jogadores antes de confirmar sua publicação na lista do gerenciador.

## Redução de recursos no Discloud

- Consultas de espera deixam de regravar o JSON completo da sala a cada pedido. O timestamp de atividade é persistido no máximo a cada 30 segundos nesse caminho; golpes novos, confirmações, trocas e presentes continuam gravados imediatamente.
- Consultas repetidas de um mesmo comando não regravam o comando já confirmado.
- Limpeza de convites expirados consulta no máximo uma vez por segundo; remoção de registros antigos roda no máximo uma vez por hora. A autorização ainda confere a validade do convite ao aceitar/entrar.
- Índices para convites, pedidos, amizades e resgates; lista de amigos usa um JOIN em vez de uma consulta por amigo.
- Resumo social na presença passa de cinco para dez segundos. Abrir/atualizar a tela continua buscando imediatamente.
- Sozinho e parado na sala, o cliente envia posição a cada cinco segundos; com outras pessoas, mantém o heartbeat de três segundos. Movimento mantém 250 ms e chat/emotes continuam prioritários. Um novo jogador pode demorar até cinco segundos para ser percebido por quem estava sozinho e parado.
- O servidor limita a 24 threads de atendimento simultâneas e tem fila TCP limitada, evitando crescimento ilimitado por conexões lentas. TCP_NODELAY reduz espera por agrupamento dos pequenos pacotes.

O benchmark local comparou o pacote publicado 0.6.2 com o novo código, usando 1.000 consultas de espera:

| Medida | 0.6.2 | 0.7.0 |
| --- | ---: | ---: |
| Regravações da sala | 1.000 | 0 |
| Comandos SQL de mutação | 2.000 | 0 |
| Tempo total local | 194,64 ms | 14,40 ms |

Esse é um teste do caminho de consulta, sem rede; não representa o consumo total do servidor nem promete redução equivalente no ping da internet. Relatório: `build/plugin-update/relay-efficiency-benchmark.json`.

## Arquivos e verificações

- Gerenciador: `scripts/gift-manager.py` e `Presentes Nordeluna.cmd`.
- Plugin: `game-plugins/Nordeluna Online/024_Gifts.rb`.
- Servidor: `server/gifts.py` e `server/relay.py`.
- Pacote Discloud: `build/discloud/gifts-0.7.0/Nordeluna-Online-Discloud.zip`.
- Backup local dos fontes: `.cache/gift-system-backups/20261108-054248`.
- Backup anterior do bundle: `Plugins/.backups/plugins-20261108-054248-506997` na pasta do jogo.

Passaram 73 testes Python e as regressões Ruby de presentes, batalha, troca, áreas e interface por toque. Incluem concorrência pelo último resgate, reinício do servidor, nick alterado, códigos inválidos/expirados, autorização, perda de confirmação, falha ao salvar, mochila/boxes cheios, limite de dinheiro, Noctgeist real, Pokédex e prevenção de reinício com save antigo. Auditoria instalada: 38 plugins, 199 arquivos Ruby, nenhum erro de sintaxe/dependências. Mapas, tilesets e metadados foram preservados. Ainda é necessário testar o novo cliente em aparelhos físicos.
