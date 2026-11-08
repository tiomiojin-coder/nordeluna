# Voltseon's Pause Menu — Nordeluna

O menu de pausa agora usa o VPM 2.2, de Voltseon, Golisopod User e ENLS,
baseado no trabalho de Yankas e Cony. Integração local Nordeluna 2.2.1.
Fonte: https://eeveeexpo.com/resources/692/

O carrossel e os nove temas usam as imagens originais do pacote. Navegue com
esquerda/direita ou cima/baixo e confirme com o botão normal do jogo. As mesmas
entradas de Input são usadas pelo teclado, pelo controle e pelo direcional do
port Android. Em **Opções → Tema do menu**, escolha entre os nove temas.

Os comandos continuam vindo de `MenuHandlers`, incluindo Online, controles,
desempenho e os aplicativos do jogo. Comandos extras recebem um ícone existente
compatível quando não têm arte própria. A entrada Online continua abrindo o
hub com amigos, missões, loja e demais funções; não há mudança no servidor.

O renderizador RE antigo foi retirado. Seu nome de plugin permanece apenas como
marcador de dependência porque os aplicativos do Nordeluna Phone o exigem.
Chamadas antigas ao menu são redirecionadas para o VPM; o livro antigo não é
aberto pelo menu de pausa. As demais telas do jogo continuam disponíveis.

Correções da integração: fechamento seguro após salvar ou viajar, retorno de
submenus, seleção antiga fora dos limites, ícones extras, preferência de tema
com valor inválido, barra EXP no nível máximo e descarte de bitmaps temporários.
Os acessos do MUI que contabilizam tempo da equipe foram preservados.

Verificações: `python scripts/test-vpm-runtime.py`. O teste carrega os cinco
arquivos reais do VPM em Ruby e simula a superfície gráfica e o Input do XP.
Verifica nove temas, 15 comandos, submenus, encerramento, seis integrantes,
ovo, desmaio, nível máximo e redirecionamento do menu antigo. O teste não
substitui uma conferência visual no aparelho Android.

Instalação: `python scripts/install-vpm.py`, com o jogo fechado. O instalador
guarda backup em `Plugins/.backups/vpm-*`, preserva os outros plugins compilados
e não modifica mapas, espécies, eventos, saves ou a publicação no GitHub.
