# Nordeluna para Android

O workflow `Build Nordeluna APK` gera um APK `arm64` instalável, com o jogo
incluído. Na primeira abertura, o app extrai os arquivos do jogo para a pasta
privada do aplicativo; as aberturas seguintes iniciam diretamente no jogo.

## Como gerar e baixar

1. Abra a aba **Actions** do repositório.
2. Selecione **Build Nordeluna APK**.
3. Clique em **Run workflow** e aguarde o sinal verde.
4. Abra a execução e baixe o artefato **Nordeluna-Android-arm64-clean-v1.0**.
5. Extraia o ZIP e use `Nordeluna-Android-arm64-clean-v1.0.apk`.
6. No telefone, permita a instalação de apps dessa fonte e abra o APK.

O APK é assinado com uma chave de depuração preservada pelo GitHub Actions.
A primeira instalação gerada com essa chave pode exigir remover a versão
anterior. Exporte o save pelo menu lateral antes de desinstalar uma versão antiga.

## Base técnica

- Engine Android: `warmwinter/mkxp-z`, fixada no commit informado no workflow.
- Bibliotecas nativas: APK oficial `uranium-android@0.2.0`, validado por SHA-256.
- Arquivo do jogo: reconstruído das partes privadas e validado por SHA-256.
- Arquitetura: `arm64-v8a`.

## Build limpa de diagnóstico

- usa somente o motor Android base e o instalador do jogo incluído;
- não altera áudio, FPS nem controles Bluetooth;
- serve para validar a inicialização do Essentials 21.1 antes de recolocar
  recursos adicionais um de cada vez.

O suporte do mkxp-z Android ainda é experimental. O APK pode compilar e instalar
corretamente, mas a compatibilidade completa de plugins do Essentials 21.1 só
pode ser confirmada executando o jogo em um aparelho Android.

