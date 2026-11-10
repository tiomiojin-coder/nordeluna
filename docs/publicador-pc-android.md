# Publicar Nordeluna para PC e Android

Abra **Publicar Nordeluna.cmd**. Abrir o programa não publica nada.

1. Salve e compile o jogo no RPG Maker XP. Feche o jogo e o editor.
2. Escolha a pasta do jogo, escreva as novidades e clique em **Conferir alterações**.
3. Confira a lista, escolha **Testers** ou **Todos**, informe o token Discloud
   no campo mascarado e clique em **Publicar para PC e Android**.

O token fica somente em memória. O login do GitHub é o do Git Credential
Manager do Windows. Não cole tokens no chat, nas notas ou em arquivos do projeto.

## Pacote rápido pelo servidor

Inclui mapas, eventos, sprites, imagens, áudio, vídeos e as tabelas compiladas
de espécies, métricas, tipos, golpes, habilidades, itens e Pokédex regional.
Um pacote atende PC e Android. Os jogadores baixam pelo menu Online e
reiniciam o jogo. Não é necessário gerar outro instalador a cada alteração.

Os PBS precisam estar compilados. Não remova IDs existentes de Pokémon,
formas, golpes, habilidades, itens ou tipos. Referências inválidas bloqueiam
a preparação. Criar o nome de uma habilidade no PBS não implementa seu efeito:
uma mecânica nova em Ruby também precisa de uma versão completa.

O programa usa pacotes cumulativos assinados, hashes, backup e restauração.
O cliente recusa a remoção de IDs já instalados. Saves não entram nos pacotes.

## Versão completa automática

Se motor, plugins, programa ou tabelas não suportadas mudarem, arquivos forem
removidos ou o pacote rápido exceder seus limites, a prévia recomenda versão
completa. O programa prepara um único jogo, aumenta as revisões, registra o
commit revisado, envia ao GitHub, acompanha as duas builds e assina os catálogos.
O PC recebe a atualização pelo launcher; o Android pede autorização para instalar.

Para **Testers**, o catálogo estável não é atualizado. O catálogo privado e
as chaves dos pacotes protegidos são publicados pelo Discloud. Com **Todos**,
o catálogo estável também é atualizado. Os arquivos estáveis gerados pelas
builds continuam sendo downloads públicos no GitHub, conforme a distribuição
atual; escolher Testers controla o catálogo, não torna o repositório privado.

Use **Retomar** após uma interrupção. Uma build enviada não é cancelada ao
parar o acompanhamento. Caso uma build falhe, confira o log e execute-a
novamente para o mesmo commit antes de retomar a publicação.

## Primeira instalação do suporte

É necessário distribuir uma versão completa com o atualizador ampliado
para PC e Android, e atualizar o servidor. O botão **Atualizar servidor**
faz backup e atualiza a aplicação existente; pode interromper sessões online.
Ele só faz isso após o clique e a confirmação no programa.

## RAM e limites

Aumentar a RAM do Discloud não habilita formatos de atualização. O sistema
mantém limites de 500 arquivos, 16 MB por arquivo, 32 MB comprimidos e 64 MB
extraídos por pacote. Mudanças maiores usam a versão completa pelo GitHub,
evitando carregar grandes distribuições na memória do servidor.

Missões, loja, presentes, avisos e moderação continuam acessíveis pelo botão
**Missões, loja e presentes**, sem precisar recompilar o jogo.
