Revisão local dos plugins — 07/11/2026
====================================

As correções estão nos fontes mantidos em `game-plugins/` e na pasta original
do jogo, em `Downloads/Pokémon Nordeluna/Pokemon Essentials v21.1 2023-07-30/
Pokemon Essentials v21.1 2023-07-30`. O bundle `Data/PluginScripts.rxdata` foi
recompilado localmente. As correções fazem parte da publicação Android 1.13;
o relay 0.6.0/revisão 5 foi publicado no Discloud com a Praça no mapa 39.

Correções aplicadas
------------------

| Plugin | Versão local | Alteração |
| --- | --- | --- |
| Customizable Battle UI | 1.0.1 | A barra de habilidade se adapta à altura do tema. Os temas 0 e 1 têm somente 32px de texto; a segunda linha do motor era desenhada em y=38 e desaparecia. Agora mostra nome do Pokémon e habilidade nos dois lados, ajusta nomes longos e atualiza uma habilidade alterada no mesmo battler. |
| Nordeluna RE Visual Core | 1.1.1 | Recria imagens de fonte, página e tema quando o bitmap em cache foi descartado; limita texto e palavras longas à largura disponível; limpa os registros de contraste ao limpar o bitmap e descarta regiões totalmente cobertas; usa segundos monotônicos nas animações e aceita duração zero. |
| Nordeluna Atmosphere | 1.1.3 | Cache de imagens verifica descarte antes de reutilizar; o renderer usa segundos monotônicos para os efeitos transitórios. |
| Nordeluna Mud Terrain | 1.0.1 | Duração e fade das pegadas usam segundos monotônicos. |
| Dublagem Nordeluna | 3.4.1 | Relógio de reprodução e redução temporária da música usa segundos monotônicos. |
| Overworld Pokemon Battles | 3.0.2 | O indicador temporário de emoção usa segundos monotônicos; seu descarte pode ser chamado novamente com segurança. |

Os relógios alterados pertencem a animações e efeitos transitórios. Não foram
alterados os tempos persistidos de respawn, atributos dos Pokémon, estatísticas
do MUI ou formato dos saves. A integração que mantém os menus nativos do CBUI
foi preservada. As mudanças locais anteriores do Online 0.5 também permanecem.

Conferência geral
----------------

`python scripts/audit-game-plugins.py --installed` conferiu os 38 plugins de
runtime: 186 arquivos Ruby, sem erros de sintaxe, dependências ausentes,
versões insuficientes ou ciclos nas dependências obrigatórias. O inventário
com versões e contagem de arquivos fica em `build/plugin-audit/audit.json`.
Essa conferência não executa todos os menus, eventos e batalhas de cada plugin.

Além dos seis plugins corrigidos, a conferência inclui Modular UI Scenes,
Enhanced Pokemon UI, Pokedex Data Page, Achievements, Arquivos System,
Controller Hints, Crafting System, Flashback System, Generation 9 Pack,
Intro Video, Light System, Mercadão Fortaleza, Moral System, No Level Cap,
No Surf, Nordeluna Battle Presentation, Nordeluna Book Integration,
Nordeluna CBUI Book, Nordeluna Event Forge, Nordeluna Online, Nordeluna Phone,
Nordeluna Services, Nordeluna Video, PC Rename, RE Bag, RE Interface, RE Menu,
RE Pokedex, RE Pokemon, Rota4Manguezal, Stardew Fishing e v21.1 Hotfixes.

Validação
---------

- `python scripts/test-plugin-regressions.py`: reproduziu o corte na implementação
  original do motor com o CBUI; depois passou em 213 verificações dos três temas,
  dos dois lados, nomes longos, mudança de habilidade, caches, texto, contraste,
  relógios e liberação dos efeitos. Usa o Ruby distribuído com o jogo e substitutos
  de tela/áudio; não mede a aparência ou a reprodução real em um telefone.
- `python -m unittest discover -s scripts/tests`: 40 testes passaram.
- `python scripts/test-online-runtime.py`: regressões do online passaram com os
  dados reais do jogo e o Generation 9 Pack.
- O compilador local preserva byte a byte, após serialização, os registros dos
  plugins não selecionados no bundle. Não abre saves.

Para repetir a compilação somente dos plugins corrigidos:

```powershell
python scripts/compile-game-plugins.py "00 RE Visual Core" "Customizable Battle UI" "Dublagem Nordeluna" "Nordeluna Atmosphere" "Nordeluna Mud Terrain" "Overworld Pokemon Battles" --install
```

O ZIP local em `build/plugin-update/Nordeluna-Plugins-Local-patch.zip` atualiza
uma cópia existente do jogo Windows; não é um APK nem uma distribuição completa.
A versão anterior do bundle foi salva na pasta `Plugins/.backups/` do jogo.
Os fontes originais dos arquivos alterados estão em `.cache/plugin-fixes-20261107/`.

Ainda precisa de teste no aparelho: troca de habilidade em batalha simples e
dupla, leitura dos nomes nos três temas, entrar e sair dos menus repetidamente,
dublagem com música, efeitos do mapa e uma sessão online prolongada. A revisão
não permite afirmar que todos os plugins estejam livres de bugs em execução.
