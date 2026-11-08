# Publicações e avisos — 0.9.1

Abra **Painel Online Nordeluna.cmd**. A janela nova se chama **Central Online Nordeluna 0.9.1**. Se a versão anterior estiver aberta com um rascunho, salve esse rascunho antes de fechá-la.

## Pacotes para testers

Na aba **Testers**, informe os **nicks online** de contas que já entraram no servidor, um por linha. Clique em **Conferir e salvar grupo**. Também são aceitos IDs de conta. A permissão fica vinculada ao ID: mudar o nick não remove a participação.

Na aba **Pacotes**, gere ou abra o ZIP assinado, escolha **Testers** e clique em **Conferir e publicar**. A prévia mostra o número do mapa, o caminho, arquivos novos/alterados e os tamanhos. A opção Testers vem selecionada inicialmente; você pode escolher Todos para uma publicação pública direta.

Os testers usam **Online → Atualizações do jogo**. O servidor verifica a identidade e a lista tanto ao consultar o pacote quanto ao baixar seus blocos. Alterar uma opção local ou saber o número da versão não libera o acesso. Remover uma conta da lista bloqueia novos downloads, inclusive os blocos restantes de um download iniciado.

Após testar, use **Testers → Atualizar publicações**, selecione o pacote e clique em **Conferir e liberar para todos**. A assinatura e os arquivos permanecem idênticos: não há recompilação ou reenvio do pacote. Uma versão pública mais recente não pode ser substituída por outra mais antiga.

O servidor mantém até três versões por público. Assim, várias versões experimentais não removem o último pacote estável. Os blocos iguais continuam compartilhados. A lista de contas e o canal ficam no banco e sobrevivem às reinicializações.

Uma conta que já instalou uma versão experimental continua com esses arquivos se for retirada do grupo. A revogação não desfaz uma instalação. Para voltar a um conteúdo anterior, publique um pacote cumulativo com número maior ou instale o APK/base correspondente. O sufixo da versão de conteúdo no identificador online ajuda a separar versões incompatíveis de batalha.

## Prévia de missões, loja e evento

1. Clique em **Carregar do servidor**.
2. Edite e salve as linhas no rascunho.
3. Clique em **Publicar rascunho no servidor**.
4. Confira a janela de prévia e use **Publicar alterações**, ou **Voltar e editar**.

A prévia identifica produtos e missões adicionados/removidos, preços antes/depois, recompensas, metas e estado ativo. Se um texto não couber na tabela, selecione a linha para ler os detalhes abaixo. Se alguém publicou outra revisão nesse intervalo, o servidor continua rejeitando a edição desatualizada.

O pacote revisado também é vinculado ao conteúdo aprovado: se o arquivo mudar depois da prévia, o programa exige outra conferência antes de enviá-lo.

## Avisos no jogo

Na aba **Avisos**, escreva uma mensagem de até 180 caracteres, escolha Aviso, Evento ou Manutenção, defina a validade em horas e o tempo na tela (6 a 12 segundos). Use **Conferir e publicar aviso**. A lista permite encerrar um aviso antecipadamente.

Os jogadores conectados recebem a mensagem junto da presença online existente. Não há nova requisição por frame. O servidor usa cache e intervalos de envio; a propagação pode levar alguns segundos. Não é uma notificação do Android nem aparece para quem está jogando completamente offline.

A faixa aparece no alto da área do jogo, tem no máximo duas linhas e desaparece sozinha. Ela aguarda o mapa estar livre de menus, diálogos e batalhas, pausa sua contagem quando fica escondida e não repete o mesmo aviso durante a sessão/reconexão. Avisos retirados ou expirados deixam a fila. Textos longos terminam em reticências.

## Instalação e verificações

O servidor precisa de **0.9.1, revisão 12**. Nenhum tester ou aviso real é criado automaticamente. Clientes anteriores continuam recebendo apenas os pacotes públicos; o cliente com plugin **0.9.1** é necessário para os testes restritos e a faixa de avisos. Ainda é preciso uma primeira versão do APK com o atualizador — publicar o servidor não atualiza o plugin dos aparelhos.

Verificações: acesso autenticado a manifestos e blocos, revogação entre processos, promoção sem alteração da assinatura, preservação do pacote estável, mudanças de nick, diferenças de preços e remoções, horários/expiração dos avisos, cache sem consultas por frame, UI Ruby com pausas/expiração/descarte de sprites, e nove abas do painel em 1080×800 e 940×720. O teste visual em Android físico fica para o APK que incluir estes plugins.

GitHub e build do APK não são disparados por estes passos de implementação.
