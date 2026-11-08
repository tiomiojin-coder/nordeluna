# Launchers PC e Android

O atalho PC abre `Nordeluna.exe`. O Android abre uma Activity independente antes
de inicializar SDL/Ruby. É possível jogar offline quando a consulta ao catálogo
falhar. A tela funciona por toque e direcional; as opções são roláveis.

## Atualizações completas

O catálogo público em `public/launcher/releases.json` é um envelope com manifesto
JSON e assinatura RSA/SHA-256, usando a chave pública que já acompanha o jogo.
A chave privada continua somente em `.cache/content-updates/private-key.json`,
fora do Git. O catálogo leva URL HTTPS, SHA-256, tamanho, código de versão,
compatibilidade online e novidades para cada plataforma e canal.

No PC, o ZIP completo atualiza motor, plugins e recursos. O launcher confere o
download inteiro antes de extrair. Rejeita caminhos indevidos, cria um diário e
backup dos arquivos substituídos e recupera alterações interrompidas ao iniciar.
Os saves ficam fora dos diretórios de atualização. O launcher em execução não é
substituído pelo ZIP; uma mudança no próprio launcher ainda pode exigir outro
instalador. O jogo precisa estar fechado, inclusive se aberto pelo Game.exe.

No Android, o launcher baixa o APK, confere hash/tamanho, nome do pacote,
código e certificado. A instalação passa pelo instalador do sistema e exige
confirmação do jogador. Só o arquivo APK verificado é compartilhado com ele
por um ContentProvider de leitura, sem expor a pasta de dados. Quando necessário,
o Android pede para autorizar instalação por essa origem. Não são baixados
plugins executáveis para dentro do aplicativo Android em execução.

As atualizações assinadas de mapas e recursos do menu Online continuam ativas.

## Saves e canais

O PC mantém dados em `%LOCALAPPDATA%/Pokemon Nordeluna/player-data/<canal>` e
os backups em `player-backups/<canal>`. O canal testers ganha uma cópia do jogo
separada da instalação estável. O Android usa `files/player-data/<canal>` no
armazenamento privado do app. Estável e testers têm IDs de pacote distintos;
podem ficar instalados juntos e o launcher direciona para o app correspondente.
Os dois APKs usam o mesmo certificado de publicação. Alterar o canal não copia
o save estável para testers. Credenciais online dentro dos saves ficam isoladas.

No primeiro uso, saves legados são copiados, sem apagar os originais. O contrato
Ruby `031_LauncherExperience.rb` direciona tanto o multi-save quanto o caminho
nativo de SaveData para o perfil correto. Metadados de data e tempo de jogo
são escritos após um save bem-sucedido. Os backups são criados antes de jogar,
antes de atualizar e, no PC, também ao encerrar. São mantidas as cinco cópias
mais recentes. A restauração valida o ZIP antes de substituir os arquivos e
cria uma cópia de segurança do estado atual.

## Preferências e diagnóstico

PC: resolução, tela cheia, volume e abertura da configuração nativa de teclado
e controle antes de começar a partida. A janela nativa usa temporariamente o
motor, sem carregar o mapa. Android: proporção, tamanho da área, volume,
controles virtuais e ocultação com controle físico. Os editores e testes de
controle existentes na engrenagem continuam disponíveis durante o jogo.

O PC monitora o processo e registra saída anormal. O Android usa o histórico de
saídas do sistema e o coletor de crashes existente. A exportação do launcher
leva apenas versão, plataforma, canal e informações de saída/sinal/memória;
nunca salva conteúdo dos saves, credenciais, conversas ou logs de rede. Os
relatórios ficam locais até o jogador escolher exportar e compartilhar.

O catálogo avisa se as versões publicadas de PC/Android diferem. Antes de
batalhas e trocas, a checagem de build existente impede misturar clientes
incompatíveis; a mensagem explica a necessidade de atualizar ambos. Testers
usam sufixo de build próprio para não disputar com o canal estável.

## Publicação

Os workflows `Build Nordeluna APK` e `Build Nordeluna PC` publicam os binários
nas Releases do GitHub. Após ambos terminarem no mesmo commit, execute
`Publicar atualizacao dos launchers.cmd`: ele confere os arquivos publicados,
assina o catálogo localmente e envia somente o catálogo ao GitHub. Para novas
versões, informe os tags e códigos com `--pc-tag`, `--android-tag`, `--pc-code`
e `--android-code`, sempre aumentando o código de cada plataforma.

Para hospedar em outro serviço, use links HTTPS diretos com
`scripts/client-release-tools.py`. A chave de assinatura continua a mesma.
O catálogo novo precisa ser publicado para o botão Atualizar oferecer o pacote.

## Verificações

Testes do núcleo Windows, das operações de backup Android, do contrato Ruby e
da assinatura/caminhos do atualizador. As builds compilam as telas Android reais.
Os testes em memória e API não substituem uma partida em aparelhos e controles
reais, nem comprovam a instalação do APK em todos os modelos de Android.
