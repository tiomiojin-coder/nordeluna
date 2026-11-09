# Reparar instalação

O botão **Reparar instalação** verifica tamanho e SHA-256 dos recursos do jogo. Saves, backups de saves e configurações válidas são preservados. Arquivos íntegros não são substituídos. O jogo precisa estar fechado.

No Windows, o catálogo assinado identifica um índice de reparação também assinado. O launcher baixa somente os trechos do ZIP correspondentes aos arquivos danificados ou ausentes, verifica seu conteúdo e só então aplica a reparação. O servidor deve aceitar HTTP Range; uma resposta com o ZIP inteiro é recusada. A revisão instalada deve corresponder à do catálogo; caso contrário, primeiro é necessário atualizar.

No Android, os recursos originais são recuperados do próprio APK instalado, sem download. Isso repara os dados extraídos do jogo; não substitui bibliotecas ou componentes do APK. Esses componentes exigem reinstalar ou atualizar o aplicativo.

As duas plataformas respeitam os arquivos de conteúdo já atualizados pelo servidor e podem recuperá-los do cache local verificado. Se tanto o arquivo atualizado quanto seu cache estiverem danificados, a reparação para com uma mensagem: não restaura silenciosamente uma versão antiga do APK ou do pacote de PC. Nesse caso é necessário recuperar o pacote de conteúdo ou atualizar o jogo completo.

Todos os arquivos de reposição são preparados e verificados antes da aplicação. Um diário e backups permitem recuperar uma reparação interrompida. Uma atualização de conteúdo pendente precisa ser concluída antes de reparar.

## Distribuição

Esta função precisa entrar em uma nova versão do launcher de PC e do APK uma primeira vez. O pacote de PC gera um índice bruto, publicado pelo workflow; o finalizador local assina esse índice e o referencia no catálogo. A chave privada permanece local.

Sprites, imagens de tilesets, dados de tilesets, mapas e eventos de mapa compatíveis podem continuar sendo distribuídos pelo painel de conteúdo Online, sem outro instalador ou APK. É necessário gerar e publicar o pacote; editar a pasta local não atualiza os jogadores automaticamente. O jogador aplica o conteúdo pelo atualizador e reinicia o jogo.

O formato atual aceita até 500 arquivos, 16 MB por arquivo, 32 MB compactados e 64 MB descompactados por pacote. Os pacotes são cumulativos. Novos plugins, funções do motor e alterações de banco de dados fora do formato de conteúdo exigem atualização completa: pelo launcher no PC ou por novo APK no Android.
