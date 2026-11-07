Android 1.13.0 (revisão 20)
==========================

Inclui o jogo atual da pasta original, com os plugins recompilados. A instalação
mantém o identificador e a chave de assinatura usados nas builds anteriores.

- Online 0.6.0: identidade e nick persistentes, Praça Central no mapa 39 em
  X=21/Y=19, personagens remotos, retorno à campanha e validação de áreas.
- Corrige o falso desacordo dos IDs: o teste de conexão preserva a configuração
  recebida do servidor. No PC, o helper Windows v2 elimina a regravação contínua
  do marcador que causava EACCES e tolera bloqueios transitórios de leitura.
- Corrige `Expected bool` ao entrar no mapa: o predicado de visibilidade devolve
  um booleano e a exibição dos nicks respeita o tipo exigido pelo motor nativo.
- MP4 no Android usa player nativo, com ajuste de proporção, pausa, retorno e
  limpeza. A preparação do APK converte os vídeos para um perfil compatível com
  decodificadores de celulares; os originais do PC são preservados.
- Ajustes nos plugins de interface, barra de habilidade, caches e efeitos:
  detalhes em `plugin-review-2026-11-07.md`.

O relay publicado é 0.6.0/revisão 5; apenas a Praça tem um mapa configurado.
Coliseu e Mercado continuam desativados até que seus mapas sejam informados.

Validação: testes Python, regressões do online no Ruby real do jogo, 213
verificações dos plugins, 22 de vídeo Ruby, 34 do estado/layout do player e
aplicação do patch sobre o motor fixado. Não substitui a verificação em aparelhos
reais nem uma partida entre dois jogadores no APK final.
