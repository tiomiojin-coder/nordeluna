# Nordeluna para Android

O workflow `Build Nordeluna APK` gera um APK `arm64` instalável, com o jogo
incluído. Na primeira abertura, o app extrai os arquivos do jogo para a pasta
privada do aplicativo; as aberturas seguintes iniciam diretamente no jogo.

## Como gerar e baixar

1. Abra a aba **Actions** do repositório.
2. Selecione **Build Nordeluna APK**.
3. Clique em **Run workflow** e aguarde o sinal verde.
4. Abra a execução e baixe o artefato **Nordeluna-Android-arm64-v1.5**.
5. Extraia o ZIP e use `Nordeluna-Android-arm64-v1.5.apk`.
6. No telefone, permita a instalação de apps dessa fonte e abra o APK.

O APK é assinado com uma chave de depuração preservada pelo GitHub Actions.
A primeira instalação gerada com essa chave pode exigir remover a versão
anterior. Exporte o save pelo menu lateral antes de desinstalar uma versão antiga.

## Base técnica

- Engine Android: `warmwinter/mkxp-z`, fixada no commit informado no workflow.
- Bibliotecas nativas: APK oficial `uranium-android@0.2.0`, validado por SHA-256.
- Arquivo do jogo: reconstruído das partes privadas e validado por SHA-256.
- Arquitetura: `arm64-v8a`.
- Os 16 caminhos legados com acentos são reempacotados como UTF-8 para que
  gráficos, tilesets, personagens e músicas sejam encontrados no Android.
- As faixas MIDI são convertidas para OGG durante a build, pois a biblioteca
  Android usada pelo motor não inclui FluidSynth em tempo de execução.
- Ao atualizar o APK, o pacote interno também é atualizado automaticamente.

O suporte do mkxp-z Android ainda é experimental. O APK pode compilar e instalar
corretamente, mas a compatibilidade completa de plugins do Essentials 21.1 só
pode ser confirmada executando o jogo em um aparelho Android.

