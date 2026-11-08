# Instalador Windows

Execute `Gerar instalador PC.cmd` no projeto. Resultado:
`build/pc/Nordeluna-PC-1.0.0-Setup.exe` e checksum SHA-256.
Para outra revisão: `python scripts/build-pc-installer.py --version 1.0.1`.
O compilador Inno Setup fica em `.cache/inno/compiler/ISCC.exe`; outra instalação
pode ser indicada com `--compiler`. O jogador não precisa de ferramentas.

O instalador inclui o jogo completo, as fontes, o transporte online Windows e
os plugins já compilados. Ele lê o projeto, monta uma cópia e não altera saves,
plugins do projeto, base de publicação do APK nem o servidor. A cópia usa o
ícone atual do port e título Pokémon Nordeluna. Não inclui PBS, editor, logs,
backups, saves, credenciais, ambientes Python ou ferramentas administrativas.

Instalação por usuário em `%LOCALAPPDATA%\Programs\Pokemon Nordeluna`, com
atalhos e diretório de trabalho correto. Essa pasta permite ao atualizador
gravar mapas sem pedir administrador. A desinstalação mantém os arquivos do
jogo para preservar dados locais; isso é informado ao jogador. Reinstalar
preserva o diretório anterior de atualizações como backup antes de instalar
uma nova base. Feche o jogo antes de instalar outra versão.

## Atualizações compartilhadas

No menu Online, use a opção de atualizar mapas e recursos. O transporte,
conta, regras para testers, assinatura RSA, conferência SHA-256 e rollback são
os mesmos do port. O servidor e o painel existentes publicam os pacotes.
O instalador registra os hashes dos recursos incluídos em
`Data/PCContentBase.json`; o atualizador PC aceita essa base local e prioriza
os hashes das atualizações já aplicadas. Pacotes continuam exigindo assinatura
do criador e caminhos permitidos. Não é permitido baixar executáveis/plugins.
Essa adaptação é aplicada somente à cópia de distribuição PC e à entrada
correspondente no bundle compilado; outros plugins são preservados.

Missões, loja, eventos, códigos e avisos continuam atualizados pelo serviço
online. Mapas, eventos de mapas e mídia compatível usam os pacotes assinados.
Novas espécies, mudanças de banco, motor ou plugins exigem outro instalador e
outro APK. O instalador não publica nenhum pacote nem dispara GitHub/Discloud.
Clientes precisam estar na mesma versão de plugins/banco para jogar juntos.
Esta entrega não rebaseia o APK antigo nem publica as mudanças locais: o
painel ainda verifica a compatibilidade antes de permitir novos pacotes.

## Verificação

`python -m unittest discover -s scripts/tests -p test_pc_installer.py`
`python scripts/test-content-updates-runtime.py --pc`

O teste Ruby usa o atualizador real com armazenamento em memória: assinatura,
download, aplicação, falha de disco, rollback e rejeição de arquivos alterados.
Não equivale a uma partida completa em outro computador.
