# Atualizar Nordeluna no Windows

Abra **Atualizar Nordeluna.cmd** na raiz do projeto. Para uso frequente, crie um atalho desse arquivo na área de trabalho. Não mova o arquivo para fora do repositório.

## Uso

1. Salve e compile as alterações do jogo no editor. Feche o editor.
2. Abra o atualizador e confira a pasta que contém `Game.ini` e `Data/Scripts.rxdata`.
3. Escolha onde salvar os APKs e clique em **Gerar novo APK e enviar**.
4. Aguarde. O programa confere os arquivos, prepara o pacote, aumenta `versionCode`, faz o commit, envia para `main` e acompanha o GitHub Actions.
5. Quando terminar, clique em **Abrir pasta do APK**. O APK completo é baixado e conferido pelo SHA-256. Pode ser instalado diretamente, inclusive por quem nunca instalou o jogo.

O programa reutiliza o login do Git Credential Manager. Não pede nem armazena tokens. Não usa serviços de IA.

## Requisitos

- Windows, Python 3.11+ com Tcl/Tk e Git for Windows instalados.
- Login no GitHub com permissão de envio para `tiomiojin-coder/nordeluna`.
- Repositório na branch `main`, sem alterações locais pendentes; GitHub Actions habilitado.
- Internet e espaço para o pacote, backup local e APK.

O botão publica os commits locais da `main`, além da atualização do jogo. Mudanças de código feitas manualmente devem ser revisadas e salvas em commit antes de usar o atualizador. Ele não descarta alterações locais e não corrige erros do jogo ou do port.

## O que entra no APK

Arquivos de execução de `Audio`, `Data`, `Fonts`, `Graphics`, `Movies` e `Plugins`, além de `Game.ini`, `mkxp.json`, `soundfont.sf2` e `achievements.dat` quando aplicável. Saves pessoais na raiz, ambientes Python `.venv`, backups, cópias em `Plugins/output`, testes/referências de desenvolvimento e o servidor/banco do plugin online não são incluídos. A pasta original do jogo não é modificada.

O jogo deve estar previamente compilado no editor: o atualizador empacota os dados atuais, não compila PBS. A conversão de áudio e compilação do aplicativo Android continuam sendo realizadas pelo workflow existente.

Cada atualização aumenta a revisão interna do APK, mantendo o nome de versão configurado no port. A instalação sobre uma versão anterior depende da mesma chave de assinatura; não exclua nem troque os secrets de assinatura do GitHub.

## Interrupções e recuperação

- Internet caiu após criar o commit? Clique em **Acompanhar / retomar envio**. Isso retoma o envio pendente, sem duplicar a atualização.
- Fechou a janela após o envio? Abra novamente e use **Acompanhar / retomar envio** para consultar a mesma build e baixar o APK.
- **Parar** interrompe a tarefa local no próximo ponto seguro. Não cancela uma build já enviada, e um envio Git em andamento precisa terminar antes de parar.
- Erro antes de criar o commit? Os arquivos substituídos são restaurados automaticamente. Erro na build? Abra **GitHub** para consultar a etapa que falhou; não existe garantia de corrigir automaticamente erros de compilação.
- Já existe uma build rodando? O programa impede criar outra atualização até ela terminar.

As preferências e o último envio ficam em `.cache/nordeluna-updater/settings.json`. Os backups do pacote anterior ficam em `.cache/nordeluna-updater/backups`. São locais e podem ocupar espaço; mantenha os necessários para recuperação. Os APKs têm pastas separadas por número da build, evitando substituir o APK de uma atualização anterior.

## Teste sem publicar

Execute `python scripts/nordeluna_updater.py --self-check` para conferir a interface sem criar commit, enviar arquivos ou iniciar build. Os testes automatizados ficam em `scripts/tests/test_updater.py`.
