# Servidor 0.10.6 — compatibilidade JSON

Corrige “Online: Resposta JSON invalida” ao conectar com os clientes atuais de PC e Android. O campo de diagnóstico `server_ms` agora contém milissegundos inteiros, conforme o leitor JSON instalado no jogo. O tempo com casas decimais introduzido em 0.10.5 tornava as respostas ilegíveis para esse leitor.

A correção exige atualizar apenas o servidor no Discloud. Não exige reinstalar o APK ou o jogo de PC. Reaproveitamento de conexões, sincronização e demais otimizações permanecem ativos.

O teste de compatibilidade lê respostas reais GET `/health` e POST `/api` e rejeita qualquer número decimal que o cliente instalado não consiga interpretar.
