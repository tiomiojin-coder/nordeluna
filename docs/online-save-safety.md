# Salvamento nas áreas online

Mapas habilitados: Praça Central 39 (70×70), Coliseu Lunar 40 (40×36) e Mercado Global 41 (38×30). Os desenhos, tilesets e eventos de passagem existentes foram mantidos. Entradas conferidas em tiles transitáveis: praça (34,59), coliseu (19,31), mercado (18,25).

O bloqueio usa o ID do mapa, mesmo em visita local sem conexão. O menu global, a tela de salvar, o sistema de slots e `Game.save` recusam salvamentos manuais com mensagem. Chamadas diretas a `SaveData.save_to_file` também são recusadas antes de gravar.

Ao carregar ou salvar um slot, `SaveData::FILE_PATH` acompanha esse slot durante a sessão. Assim, comprovantes, trocas e resgates gravam no mesmo arquivo usado por Continuar. Falhas ao carregar restauram o destino anterior; iniciar um jogo novo restaura o caminho padrão, protegendo o slot da aventura anterior.

Antes de entrar, o jogo confirma o save da campanha e o ponto de retorno. As gravações técnicas de trocas e recompensas continuam necessárias para evitar perda ou duplicação: o arquivo temporário é validado e recebe o `map_factory`, `game_player` e `map_metadata` do ponto seguro previamente salvo. Os Pokémon, itens, variáveis, moedas e comprovantes atuais continuam no novo save. Nenhum teleporte ou alteração dos objetos de mapa/personagem em execução é feito para gravar.

Se o retorno ou o save anterior não puder ser validado, a gravação falha e o arquivo anterior é preservado. O carregamento de saves legados com âncora válida continua restaurando a campanha antes de inicializar o mapa. Não é criado um destino arbitrário para saves sem ponto de retorno.

Os testes Ruby cobrem os três mapas, menus/slots, escrita direta, salvamentos técnicos, trocas, preservação de progresso, ausência de teleporte, disco cheio e recuperação após fechamento.
