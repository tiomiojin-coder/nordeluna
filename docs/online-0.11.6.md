# Online 0.11.6 — entrada segura na praça

Antes do transporte, o cliente confirma a validade da sessão com o servidor. Se a sessão expirou ou foi perdida durante o salvamento da campanha, renova a presença uma vez, preservando o mesmo ponto de retorno e sem repetir o fluxo de entrada.

Falhas de rede e bloqueios de moderação continuam cancelando o transporte e restaurando a campanha. A renovação aplica-se apenas à presença na praça; não repete compras, trocas ou ações de batalha.

Os testes do runtime cobrem reinício do servidor, perda da sessão durante o save, indisponibilidade da rede e bloqueio pela moderação. Este ajuste está no plugin do cliente e precisa entrar no pacote atualizado de PC/Android.
