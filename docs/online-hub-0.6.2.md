# Online 0.6.2 — menu único e cartões para celular

Atualização instalada nos fontes e no bundle compilado do jogo local. Servidor Discloud atualizado para **0.6.2 / revisão 7**, com backup e verificação de preservação do banco (23 registros de salas e quatro contas). Nenhum envio ao GitHub ou build de APK foi executado.

## Como usar

No menu de pausa existe uma única entrada **Online**, com contador de pedidos/convites pendentes. Ela reúne:

- Praça central.
- Amigos e convites.
- Jogadores próximos.
- Chat da sala.
- Batalhas e trocas, incluindo recuperação de troca pendente.
- Emotes.
- Meu perfil e status: nick online e disponibilidade.
- Conexão: salas privadas, teste, diagnóstico, servidor e saída da praça.

Os painéis compartilham fundo azul escuro, destaque ciano, botões com altura de 34 pixels lógicos e indicação da opção selecionada. Listas longas têm barra de rolagem e podem ser arrastadas no celular. Teclado e controle usam cima/baixo, confirmar e voltar. Painéis com poucas opções ficam menores e centralizados.

Na praça, **toque no corpo de outro jogador e solte o dedo** para abrir o cartão com nick, estado, sala e ações de adicionar amigo, convidar para batalha ou troca. Um arrasto, toque prolongado, movimento do personagem, menu aberto ou toque nos cantos inferiores reservados ao controle virtual não abre cartões. Se houver jogadores sobrepostos, uma lista permite escolher. A opção **Jogadores próximos** oferece uma alternativa para teclado, controle e áreas cobertas pelos botões virtuais.

O cartão usa convites confirmáveis. Amigos podem ser convidados à distância; jogadores sem amizade precisam estar na mesma sala, mapa e versão, a no máximo oito passos de distância em Manhattan. O servidor verifica essa condição, além da identidade e autorização do dono da sala. Aceitar o convite mantém a seleção de equipe/oferta e todas as confirmações de batalha/troca. Nada é transferido automaticamente pelo toque.

## Estados sobre o personagem

O nick permanece acima do personagem; uma segunda linha pequena indica **Disponível**, **Ocupado**, **Em batalha** ou **Em troca**, com cores consistentes. O estado muda sem recriar o sprite ou invalidar o cache de aparência. A disponibilidade manual fica no save; atividades de batalha/troca são temporárias.

Ao entrar na praça, a presença social é ativada para esta sessão. Durante PvP/trocas, um heartbeat de até três segundos mantém a presença, usando somente o transporte ocioso. Ele não concorre com os pedidos da partida. Uma falha desse heartbeat não provoca transferência de mapa dentro da batalha; a reconexão usa o fluxo normal de retorno.

O servidor mantém o protocolo 1 e aceita clientes anteriores nos fluxos compatíveis. Clientes antigos sem estado social aparecem disponíveis enquanto têm presença de mapa válida. Os novos menus e cartões **exigem o jogo atualizado**: publicar o servidor não modifica a interface de um APK já instalado.

## Publicação e arquivos

- Pacote publicado: `build/discloud/online-hub-0.6.2/Nordeluna-Online-Discloud.zip`.
- Resultado verificado: `.cache/discloud-deploy/online-hub-0.6.2-status.json`.
- Backup antes do deploy: `.cache/discloud-deploy/20261108-034642-268253/before-update.zip`.
- Backup dos fontes locais: `.cache/online-hub-backups/20261108-034943`.
- Backup do bundle anterior: `Plugins/.backups/plugins-20261108-034943-528889` na pasta do jogo.
- Prévias de layout, renderizadas com fonte aproximada: `build/chat-layout/online-menu.png` e `online-cartao.png`.

Os IDs do servidor continuam praça 39 e interiores desativados. Mapas, tilesets, metadados e saves não foram substituídos.

## Validação

64 testes Python passaram, incluindo escopo/distância de convites, autorização, estados atualizados com cache de aparências e preservação de trocas concluídas. Os testes Ruby exercitaram os métodos reais de menus e desenho, navegação, gesto de arrasto, toque ao soltar, estados, descarte dos sprites, transporte serializado e ausência de transferência durante falha de presença. As regressões anteriores de batalha, troca, áreas e chat também passaram.

Auditoria: 38 plugins, 198 arquivos Ruby, nenhum erro de sintaxe/dependências. Ainda não foi feita uma partida entre dois aparelhos com esta interface nem uma nova build Android.
