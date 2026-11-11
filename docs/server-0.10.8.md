# Servidor 0.10.8 — tráfego e praça

- Compressão gzip negociada para respostas JSON a partir de 1 KiB, somente quando reduz o tamanho. Clientes que não pedem gzip recebem JSON normal. Android HttpURLConnection negocia e descomprime gzip por padrão; o transporte atual não altera esse cabeçalho.
- Conexões podem servir até 128 respostas, em vez de 16. Espera ociosa limitada a cinco segundos; 16 conexões persistentes entre 32 trabalhadores, preservando 16 vagas para novas requisições. Nenhum aumento de plano ou RAM contratado.
- A praça filtra membros uma única vez por atualização e seleciona os 40 mais próximos antes de construir seus registros. O chat mantém a contagem dos participantes de todos os mapas da sala. Aparências reutilizam sua impressão digital até o nome ou sprite mudar.
- Mantidos JSON com números inteiros, autenticação e revogação de testers, moderação, reservas de trocas e SQLite WAL com `synchronous=FULL`. A atualização não reduz a durabilidade das transações.

## Verificação local

`python scripts/benchmark-online-server.py` cria somente contas e SQLite temporários. Não acessa o servidor público. Em 500 atualizações por cenário, nesta máquina:

| Jogadores simulados | Mediana antes | Mediana depois | P95 antes | P95 depois |
|---|---:|---:|---:|---:|
| 40 | 0,260 ms | 0,214 ms | 0,455 ms | 0,240 ms |
| 150 | 0,485 ms | 0,336 ms | 0,754 ms | 0,494 ms |

Os valores incluem lógica de mapa e serialização JSON, não rede. Uma resposta de aproximadamente 11,5 KiB caiu para 2,7 KiB com gzip nível 1, custo mediano de compressão de cerca de 0,076 ms neste teste. Não equivalem a uma promessa de ganho no ping.

Antes da publicação, cinco requisições públicas com conexões novas tiveram mediana de 506 ms. Uma conexão HTTPS reutilizada levou 511 ms na primeira resposta e 211–231 ms nas seguintes, com diagnóstico de processamento arredondado a 0 ms. Essas medições refletem a rota desta máquina até a hospedagem, não a internet de todos os jogadores. Reduzir esse piso exige investigar localização da hospedagem e rota de rede.

Referência de compatibilidade: https://developer.android.com/reference/java/net/HttpURLConnection#performance
