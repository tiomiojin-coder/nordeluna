Mapas sociais locais do Nordeluna
================================

| Mapa | ID | Tamanho | Tileset |
| --- | --- | --- | --- |
| Praça Central | 39 | 70×70 | 34, Salvador — Nordeste (`NordesteTileset`) |
| Coliseu Lunar | 40 | 40×36 | 24, Inside Geral |
| Mercado Global | 41 | 38×30 | 24, Inside Geral |

A praça mantém seu ID. Os dois interiores aparecem como filhos da Praça na
árvore do RPG Maker XP. Nenhuma imagem ou configuração global dos tilesets é
alterada. Troncos, paredes, copas, telhados e móveis usam peças completas; suas
prioridades nativas determinam as camadas superiores.

O desenho inclui floresta de contorno, fonte, pavimento em forma de lua,
recepção, Jardim das Fases e alameda de convivência. O Coliseu tem área de
encontro, assentos, preparação de equipe, descanso e terminal. O Mercado tem
balcão de trocas diretas, prateleiras, itens de viagem e terminal.

Há 49 eventos: 23 na praça e 13 em cada interior. A memória do enigma usa as
self switches A–D do evento 30 do mapa 39, preservadas pelo save normal. O
descanso cura a equipe e mantém o retorno da campanha. Batalhas, trocas,
confirmações e comprovantes continuam usando as rotinas existentes do Online.
O Mercado não acrescenta anúncios globais ou entregas automáticas.

Entradas e saídas
----------------

- Chegada online na Praça: X=34, Y=59, olhando para cima (8).
- Porta do Coliseu na Praça: X=17, Y=17; chegada no mapa 40 em X=19, Y=31.
- Porta do Mercado na Praça: X=51, Y=19; chegada no mapa 41 em X=18, Y=25.
- Saídas dos interiores ficam nos tapetes ao sul. As chegadas não pisam em
  eventos de saída, evitando um retorno imediato.
- A antiga chegada da Praça, X=21/Y=19, continua transitável.

Revisão local
-------------

`python scripts/create-social-maps.py` gera o pacote em `build/social-maps`.
`python scripts/validate-social-maps.py` usa `Game_Map.passable?` e
`playerPassable?` reais do Essentials para conferir trajetos, colisão,
balcões, alcance dos eventos, spawns e destinos. A serialização é relida no
Ruby real e todos os registros de mapas alheios são preservados.

As prévias `map-39.png`, `map-40.png` e `map-41.png` mostram os tiles do projeto.
As versões com sufixo `-events` identificam cada evento. O renderizador local
usa Pillow; ele não gera nem substitui artes do jogo. A validação automática
não substitui andar pelos mapas e interagir no jogo real.

O pacote também atualiza apenas as seções 39–41 de `PBS/map_metadata.txt` e os
registros correspondentes de `Data/map_metadata.dat`. Não é necessário
recompilar todos os PBS ou mexer em espécies, golpes, itens ou saves.

Ativação online dos interiores
-----------------------------

O servidor publicado ainda informa `plaza=39, coliseum=null, market=null`.
Essa configuração continua válida para a Praça. As portas mostram uma
mensagem quando o interior ainda não foi autorizado. No teste do editor,
com `$DEBUG` ativo e sem sessão online, é possível visitar os interiores.

Para liberar a presença online nos três mapas, cliente e servidor precisam
usar juntos `plaza=39, coliseum=40, market=41`. Há um cliente preparado em
`build/social-maps/online-activation`, separado da instalação atual. Essa
variante altera `COLISEUM_MAP_ID` para 40 e `MARKET_MAP_ID` para 41. O servidor
precisa receber os mesmos IDs em `NORDELUNA_ONLINE_AREAS` ou em `DEFAULT_AREAS`.
Não instale só uma metade: a validação exige os mesmos IDs nos dois lados.

Nenhum deploy, push ou build remota faz parte desta alteração local.
