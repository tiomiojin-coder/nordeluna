# Conexão online

PC, Android e servidor reaproveitam conexões HTTP completas. Falhas, cancelamentos e respostas incompletas fecham a conexão; operações de troca e compra não são repetidas automaticamente.

O servidor reserva no máximo oito conexões persistentes entre 24 trabalhadores. Cada conexão tem três segundos de espera e até 16 respostas, liberando espaço para novos jogadores. O transporte Windows recebe notificações de arquivos, com verificação periódica de segurança, em vez de consultar a pasta a cada 50 ms.

Movimento pode ser enviado a cada 150 ms. Parado, o cliente consulta novidades a cada 500 ms com outros jogadores ou 1,5 segundo sozinho. Mensagens e emotes não esperam esse intervalo. Continua existindo somente uma requisição de praça em andamento por cliente.

O diagnóstico mostra a última latência, média das últimas 20 amostras, amplitude entre amostras e tempo de processamento informado pelo servidor. Os testes locais conferem reaproveitamento real das conexões em PC/Java e limites do servidor. Não representam uma medição da internet dos jogadores; distância ao datacenter, Wi-Fi e operadora continuam influenciando o ping.
