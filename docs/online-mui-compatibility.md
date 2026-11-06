# Online 0.2.1: compatibilidade com Enhanced Pokemon UI

O plugin MUI acrescenta `last_update_time`, `legacy_data` e `shiny_leaf` aos Pokémon.
O codec 0.2.0 recusava qualquer campo não reconhecido; mesmo aceitando o relógio,
o histórico ainda conteria tempos fracionários não suportados pelo JSON inteiro.

O codec 0.2.1:

- Omite o relógio de processo `last_update_time` do pacote e o reinicia com o
  `System.uptime` local ao reconstruir o Pokémon. Não altera o relógio do original.
- Preserva a folha/coroa brilhante e os contadores de histórico do MUI.
- Transporta tempos fracionários finitos por uma representação decimal marcada,
  sem mudar o protocolo JSON ou serializar objetos Ruby pela rede.
- Rejeita NaN, infinito, contadores inválidos e campos desconhecidos de outros plugins.
- Usa o endereço público `https://nordeluna-online.discloud.dev` como padrão,
  preservando o endereço personalizado que já estiver salvo pelo jogador.

Windows e Android devem usar a mesma atualização: `BUILD=nordeluna-online-2026-11-06-3`.
O relay 0.2.0/revisão 2 existente permanece compatível; não precisa substituir o banco
ou publicar outro servidor para essa correção.

## Verificação local (Windows)

`python scripts/test-online-runtime.py` executa os testes existentes de codec,
trocas e batalhas do projeto, depois carrega o bloco real `Pokemon` do MUI e verifica
relógios, histórico fracionário, shiny leaf, roundtrip JSON, escrow e dados inválidos.
O teste usa a DLL Ruby do jogo; não abre nem grava os saves.

`python scripts/compile-online-plugin.py --install` recompila apenas o plugin Online
na cópia local configurada. Confere que os outros plugins compilados permanecem
iguais, cria backup do bundle anterior e instala atomicamente `Data/PluginScripts.rxdata`.
Os fontes precisam estar corrigidos antes desse comando. O mesmo processo gera
um ZIP de atualização Windows em `build/online-update`.

Os testes automatizados não substituem uma partida entre dois aparelhos com os
plugins completos. Se surgir outro campo desconhecido, investigue sua origem e
semântica antes de adicioná-lo ao codec; não desative a proteção geral.
