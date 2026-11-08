# Central Online Nordeluna 0.9.0

Abra **Painel Online Nordeluna.cmd**, na raiz do port:

`C:\Users\tiomi\OneDrive\Documentos\Programação\Nordeluna-iOS`

O servidor continua em Python. O programa Windows permite editar pelos formulários ou por um **arquivo Ruby real**, interpretado pelo Ruby instalado junto do jogo. O servidor recebe os dados validados, sem precisar executar Ruby.

## Missões, loja e evento comunitário

1. Informe o token no campo mascarado. Ele fica apenas na memória da janela.
2. Clique em **Carregar do servidor**.
3. Selecione ou crie uma missão/produto. Após editar, clique em **Salvar / adicionar no rascunho**. O formulário da loja tem rolagem.
4. Na aba do evento, use **Salvar evento no rascunho**.
5. Clique em **Publicar rascunho no servidor**.

O jogo consulta os dados ao abrir a loja, as missões ou o desafio novamente. Não é preciso reiniciar o servidor nem gerar APK para esses ajustes. As moedas são controladas pelo servidor.

As missões disponíveis contam visitas diárias (`visit`, meta 1), batalhas confirmadas com pelo menos dois turnos (`battle`) ou trocas concluídas (`trade`). Novos tipos de atividade exigem suporte no cliente e no servidor. A contagem diária considera o dia em UTC−3, inclusive atividades anteriores à publicação da missão.

O mesmo ID preserva o resgate já feito naquele dia. Alterar o prêmio não paga outra vez a quem já recebeu. Use IDs novos para missões novas. O tipo de um ID publicado não pode ser trocado. Eventos comunitários usam um ID por edição; para mudar meta/prêmio, crie outro ID. Encerrar um evento não apaga o progresso anterior nem os emblemas conquistados.

Na loja, os IDs de espécies, formas, itens e golpes são conferidos com os PBS locais. O cliente precisa já conhecer o conteúdo oferecido. Remover um produto não invalida compras anteriores ou sua recuperação. **Noctgeist foi removido da loja inicial.**

O histórico permite carregar uma edição anterior no rascunho e publicá-la como nova revisão. Uma edição não pode sobrescrever outra publicação mais recente sem carregar o servidor novamente.

## Editar em Ruby

Na aba **Arquivo Ruby**, exporte `conteudo-online.rb`, edite e importe novamente. Exemplo de missão dentro de `missions`:

```ruby
'batalhas_da_praca' => {
  'title' => 'Conclua cinco batalhas',
  'kind' => 'battle',
  'target' => 5,
  'coins' => 60,
  'enabled' => true
}
```

O rascunho local fica em `build/admin/conteudo-online.json`. O arquivo Ruby não vai dentro do APK: o painel publica os dados dele. A aba **Códigos de presente** abre o editor já existente para criar/encerrar códigos, limites e recompensas.

## Mapas, eventos e recursos pelo servidor

É necessária **uma primeira instalação de APK com o plugin 0.9.0 e sua chave pública**. O APK atualmente nos aparelhos não ganha o atualizador só com a publicação no Discloud. Nenhuma build foi disparada nesta alteração.

A base inicial foi registrada localmente. O atualizador de APK e o script de preparação registram novamente os hashes **do ZIP efetivamente empacotado**, para incluir suas edições até a primeira build. Depois dessa primeira instalação:

1. Edite e salve os mapas no RPG Maker XP. Compile os PBS alterados pelo jogo quando necessário e feche o editor antes de preparar o pacote.
2. Abra **Mapas e recursos** no painel.
3. Escolha um número de pacote maior que o anterior, título e novidades.
4. Clique em **Gerar pacote das alterações**, depois em **Publicar pacote**.
5. No jogo, abra **Online → Atualizações do jogo**, confirme o download e depois feche totalmente e reabra o aplicativo.

O pacote é cumulativo a partir da base: o jogador pode ir direto ao último, sem instalar os intermediários. Inclui mapas `MapNNN.rxdata`, `MapInfos`, `Tilesets`, eventos comuns, metadados/conexões/encontros de mapas, imagens, áudio e vídeos permitidos. Os eventos dentro dos mapas seguem junto com o mapa. A base não permite remover arquivos; para retirar um mapa da exploração, remova suas entradas/acessos do projeto e publique os dados correspondentes.

Mudanças no motor, plugins Ruby e dados de espécies/itens/golpes **continuam exigindo um APK novo e preparação de outra base**. Novas funções de missão também precisam de código. Não se pode oferecer uma espécie desconhecida aos clientes antigos apenas alterando a loja.

Os pacotes usam assinatura RSA-2048/SHA-256 com chave pública incorporada no cliente. O download usa blocos de 16 KB; arquivos existentes não mudam durante a sessão. No início seguinte, todos os hashes e originais são conferidos antes de aplicar. Existe backup e registro para restaurar uma instalação interrompida. Os caminhos de saves, scripts, plugins e executáveis não são aceitos. Uma atualização não consegue garantir compatibilidade de qualquer evento criado pelo autor: teste a exploração e as transições antes de disponibilizar.

Limites atuais: 500 arquivos; 16 MB por arquivo; 32 MB comprimidos e 64 MB extraídos por pacote. O servidor retém as três versões publicadas mais recentes, compartilha blocos iguais e limita a três envios pendentes. O download e a publicação só executam quando solicitados; não acrescentam consultas ao movimento normal no mapa.

**Guarde uma cópia particular de `.cache/content-updates/`**, que contém a chave privada, a base e o histórico dos arquivos alterados. Não envie essa pasta ao GitHub nem aos jogadores. A chave privada não está no pacote do Discloud. Os pacotes de distribuição ficam em `build/content-updates/`.

## Aparência e validação

O nick agora tem fundo transparente e contorno, status mais próximo, sem o quadrado solto. Os nomes permanecem dentro da tela após os ajustes para multidões. Há rolagem nas abas de edição para janelas menores.

Verificações locais: testes de servidor e transações, Ruby real para navegação/loja e criptografia, instalação em memória com recuperação de interrupção/falha de disco, auditoria dos plugins compilados, formulários em 1080×800 e 940×720. O fluxo completo de download/reinício ainda precisa ser testado em um Android com o primeiro APK que inclua o atualizador.

O diretório original do jogo é:

`C:\Users\tiomi\Downloads\Pokémon Nordeluna\Pokemon Essentials v21.1 2023-07-30\Pokemon Essentials v21.1 2023-07-30`
