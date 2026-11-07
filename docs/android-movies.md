Vídeos MP4 no Android
====================

O erro `Failed loading user32: dlopen failed` vinha do plugin Nordeluna Video:
`pbVideo` selecionava incondicionalmente o FFplay/Win32, inclusive no Android.
A presença de `Win32API` não comprova que o sistema seja Windows, pois o port
também expõe essa interface de compatibilidade.

Correção local
--------------

- Nordeluna Video 1.3.0 seleciona `AndroidPlayer` quando `System.is_android?`
  ou a plataforma Ruby identifica Android. As chamadas dos eventos continuam
  iguais: `pbVideo("001")`, `pbVideo("001", :mapa)` etc.
- `AndroidMovieBridge.java` usa o MediaPlayer e uma TextureView em um diálogo
  acima do jogo. Mantém proporção, centraliza a imagem, permite segurar para
  pular por toque/teclado/controle e não mostra os controles virtuais sobre o filme.
- Preserva volume, perfil mudo/misturado e fades de entrada/saída. A opção
  “Silenciar jogo” também é aplicada ao player; ele não pede foco de áudio por
  conta própria. A política de mistura continua sendo a do aplicativo.
- Minimizar ou perder o foco de áudio pausa a reprodução. Os recursos são
  liberados ao concluir, pular, cancelar ou falhar. Erros de preparação e um
  decodificador que para de avançar encerram a espera com mensagem.
- Ruby e Java trocam dados por arquivos pequenos em `.nordeluna-movie-bridge`;
  não há execução de comandos, carregamento de DLL ou nova biblioteca nativa.
  Sessão, tamanho do pedido, arquivo permitido e opções são validados.
- Um APK anterior, sem essa ponte, mostra uma mensagem pedindo atualização;
  nunca tenta reproduzir o vídeo usando `user32` no Android.
- O bloco `ensure` de reprodução restaura áudio e brilho após erros. O player
  Windows foi preservado.

Preparação dos arquivos no APK
-----------------------------

Os quatro MP4s locais usam H.264/AAC. `Movies/001.mp4` tem 1932×1080 e nível
4.2; essa largura pode ultrapassar o limite de decodificadores de alguns aparelhos.
`scripts/prepare-android-movies.py`, chamado na preparação da build Android,
normaliza somente a cópia extraída para H.264 Main nível 3.1, yuv420p, até
1280×720, 30 FPS, áudio AAC estéreo e `faststart`. Mantém proporção e nomes;
aceita vídeos sem faixa de áudio. Falha de conversão interrompe o empacotamento.
Os vídeos originais do jogo Windows permanecem intactos.

A workflow copia `MovieMailbox.java` e `AndroidMovieBridge.java` para o projeto
Android antes da compilação. A próxima atualização precisa registrar esses
fontes e os scripts da preparação, além de reempacotar os dados atuais do jogo.
O atualizador local já incrementa o versionCode ao preparar uma publicação.
Nada foi enviado ao GitHub ou ao Discloud, e nenhum APK foi gerado nesta correção.

Validação local
---------------

- Patch aplicado sem erro à revisão fixada do motor
  `17a5ec6cb3e8d2de05a82451bc4910f36517d322`.
- As duas classes Java novas compilam com Java 8 e as definições de APIs do
  Android 4.1, anteriores ao Android mínimo do aplicativo (API 21).
- `python scripts/test-video-runtime.py`: 22 verificações no Ruby do jogo,
  cobrindo seleção da plataforma, opções, erro nativo, APK antigo, timeout e
  restauração do áudio/brilho.
- `python scripts/test-movie-player.py`: métodos reais de proporção, volume,
  fades, pausa, pular, timeout e limpeza, com substitutos de mídia e tela.
- `python -m unittest discover -s scripts/tests`: inclui o protocolo Java real,
  caminhos UTF-8, pedidos inválidos, cancelamento, callbacks atrasados e conversão
  real com FFmpeg de um vídeo de 1932 pixels e de um vídeo sem áudio.
- As regressões de controles virtuais continuam passando.

O bundle local `Data/PluginScripts.rxdata` foi recompilado com o Video 1.3.0,
preservando as outras melhorias pendentes e os saves. Os fontes anteriores
estão em `.cache/video-fix-20261107/`; o bundle anterior em `Plugins/.backups/`.

Ainda é necessário reproduzir os filmes num APK novo em um Android físico.
Os testes de tela/mídia usam substitutos; não validam o decodificador do aparelho.

Referências de API: [MediaPlayer](https://developer.android.com/reference/android/media/MediaPlayer)
e [TextureView](https://developer.android.com/reference/android/view/TextureView).
