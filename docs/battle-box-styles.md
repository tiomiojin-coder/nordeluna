# Caixas de batalha selecionáveis

No jogo, abra **Op??es ? Caixa de batalha**. Use esquerda/direita no teclado,
controle Bluetooth ou direcional virtual do Android. Uma ?nica prefer?ncia muda
as caixas do jogador e do advers?rio juntas e ? gravada com as op??es normais.
A mudan?a vale na pr?xima batalha, incluindo batalhas online. N?o muda regras,
Pok?mon, habilidades, sele??o de alvos, trocas ou pacotes de rede.

A vers?o 1.1.1 substitui tamb?m a antiga entrada "Tema da batalha", eliminando
configura??es concorrentes. Prefer?ncias da vers?o com seletores separados s?o
migradas: a escolha personalizada do jogador tem prioridade, seguida pela do
advers?rio. A partir da?, ambos os lados sempre usam o mesmo estilo.

Estilos disponíveis: **Padrão**, **Vermelho**, **Azul**, **Emerald** e **SwSh
adaptado**. Padrão preserva as caixas usadas anteriormente, inclusive a escolha
do tema vermelho/azul existente. Os dois temas de cores são do CBUI, não dos jogos
Red/Blue de Game Boy. O estilo SwSh é uma adaptação em pixel art de BiggusWeeabus,
não uma reprodução idêntica do jogo de Switch.

## Recursos pesquisados

* [Customizable Battle UI — Toxillian](https://eeveeexpo.com/resources/1312/):
  já instalado no projeto; recebeu a integração de caixas 1.1.1.
* [Battle Databox Styles — BoydALoyd](https://eeveeexpo.com/resources/1930/):
  avaliado localmente. Não foi instalado junto do CBUI porque substitui o mesmo
  método e não fornece os gráficos. A funcionalidade de seleção independente foi
  implementada na integração existente, sem redistribuir o código desse pacote.
* [Emerald UI Pack 1.2 — Voltseon](https://eeveeexpo.com/resources/965/):
  selecionados somente fundos das caixas, barras HP/EXP e números. As demais
  interfaces, mapas, scripts e battlebacks do pacote não foram instalados.
* [SwSh-Inspired Battle Interface — BiggusWeeabus](https://eeveeexpo.com/resources/860/):
  sete imagens de caixas/barras/números integradas.
* [Black 2/White 2 — HP Bars, GameMaster12](https://www.spriters-resource.com/ds_dsi/pokemonblack2white2/asset/207786/):
  folha localizada; download recusado pelo site com HTTP 403 nesta sessão.
  Estilo **não instalado** e não substituído por um desenho de Black/White.
* Let's Go Pikachu/Eevee: não foi encontrado um pacote pronto verificável para
  Essentials 21.1. Estilo **não instalado**.

## Integração e verificação

O adaptador de compatibilidade Nordeluna CBUI Book 1.1.1 deixa o renderizador da
caixa escolhida funcionar, preservando o caminho anterior quando Padrão está
selecionado. A seleção verifica recursos uma vez ao criar cada caixa; imagens
faltando fazem o estilo completo voltar ao padrão. HP/EXP mantêm as animações e
a propriedade de bitmaps do Essentials. O texto dos novos estilos reduz a fonte
para acomodar nomes longos. Os arquivos seguem nomes com caixa consistente para
Android/Linux.

`python scripts/test-battle-box-styles.py` exercita 60 instâncias com os métodos
reais de caixa do Essentials, camadas de apresentação/compatibilidade, cinco
estilos, 1/2/3 Pokémon por lado, preferências antigas/invalidas, serialização,
animações HP/EXP e descarte de bitmaps. A superfície gráfica é simulada;
validação no aparelho Android ainda é necessária.

Instalação local com backup: `python scripts/install-battle-box-styles.py`,
seguido da recompilação de `Customizable Battle UI` e `Nordeluna CBUI Book`.
Nenhum servidor, GitHub ou workflow precisa ser alterado por estas opções visuais.

Para conferir tamb?m se o c?digo compilado instalado corresponde ? integra??o,
use `python scripts/test-battle-box-styles.py --installed`. Feche e reabra o jogo
ap?s instalar a atualiza??o; a inst?ncia j? aberta continua usando scripts antigos.


## Hotfix 1.1.2

Removes Font.shadow access: RPG Maker XP does not expose that property.
The graphics fixture now omits shadow/shadow= to reproduce this failure.
Unified player/opponent selection is preserved. Installed-bundle checks passed.
