# Nordeluna para Android

O workflow `Build Nordeluna APK` gera um APK universal instalável, com o jogo
incluído. Ele contém código nativo `arm64-v8a` para aparelhos físicos e
`x86_64` para emuladores como o BlueStacks. Na primeira abertura, o app extrai
os arquivos do jogo para a pasta privada do aplicativo; as aberturas seguintes
iniciam diretamente no jogo.

## Como gerar e baixar

1. Abra a aba **Actions** do repositório.
2. Selecione **Build Nordeluna APK**.
3. Clique em **Run workflow** e aguarde o sinal verde.
4. Abra a execução e baixe o artefato **Nordeluna-Android-universal-v1.2**.
5. Extraia o ZIP do artefato e use `Nordeluna-Android-universal-v1.2.apk`.
6. No telefone, permita a instalação de apps dessa fonte e abra o APK.

O APK é assinado com a chave de depuração criada pelo GitHub Actions. Uma
instalação da versão 1.1 ou anterior precisa ser removida antes da 1.2, pois
as chaves antigas eram temporárias. A partir da 1.2, o workflow preserva a chave
de assinatura para permitir atualizações. Exporte o save pelo menu lateral antes
de desinstalar uma versão antiga.

## Base técnica

- Engine Android: `warmwinter/mkxp-z`, fixada no commit informado no workflow.
- Bibliotecas nativas: APK oficial `uranium-android@0.2.0`, validado por SHA-256.
- Arquivo do jogo: reconstruído das partes privadas e validado por SHA-256.
- Arquiteturas: `arm64-v8a` para aparelhos e `x86_64` para emuladores.

## Correção da versão 1.2

- núcleo x86_64 nativo para evitar o fechamento durante a inicialização no
  BlueStacks;
- mantém o núcleo ARM64 usado em aparelhos Android modernos;
- o workflow confere as bibliotecas essenciais das duas arquiteturas antes de
  publicar o APK.

## Recursos da versão 1.1

- contador de FPS habilitado por padrão no canto superior direito;
- controles Bluetooth/USB pelo SDL e mapeamento alternativo para controles
  Android sem perfil reconhecido;
- foco de áudio no canal de mídia do Android;
- músicas MIDI e o MP3 isolado convertidos para OGG durante a compilação;
- mais canais simultâneos para efeitos sonoros e cache de caminhos para nomes
  com diferenças de maiúsculas, minúsculas ou acentos.

O suporte do mkxp-z Android ainda é experimental. O APK pode compilar e instalar
corretamente, mas a compatibilidade completa de plugins do Essentials 21.1 só
pode ser confirmada executando o jogo em um aparelho Android.

