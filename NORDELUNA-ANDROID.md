# Nordeluna para Android

O workflow `Build Nordeluna APK` gera um APK `arm64` instalável, com o jogo
incluído. Na primeira abertura, o app extrai os arquivos do jogo para a pasta
privada do aplicativo; as aberturas seguintes iniciam diretamente no jogo.

## Como gerar e baixar

1. Abra a aba **Actions** do repositório.
2. Selecione **Build Nordeluna APK**.
3. Clique em **Run workflow** e aguarde o sinal verde.
4. Abra a execução e baixe o artefato **Nordeluna-Android-arm64**.
5. Extraia o ZIP do artefato e envie `Nordeluna-Android-arm64.apk` ao Android.
6. No telefone, permita a instalação de apps dessa fonte e abra o APK.

O APK é assinado com a chave de depuração criada pelo GitHub Actions. Uma
compilação futura pode exigir desinstalar a anterior; exporte o save pelo menu
lateral antes de trocar de versão.

## Base técnica

- Engine Android: `warmwinter/mkxp-z`, fixada no commit informado no workflow.
- Bibliotecas nativas: APK oficial `uranium-android@0.2.0`, validado por SHA-256.
- Arquivo do jogo: reconstruído das partes privadas e validado por SHA-256.
- Arquitetura: `arm64-v8a`.

O suporte do mkxp-z Android ainda é experimental. O APK pode compilar e instalar
corretamente, mas a compatibilidade completa de plugins do Essentials 21.1 só
pode ser confirmada executando o jogo em um aparelho Android.

