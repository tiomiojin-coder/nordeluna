# Nordeluna Online no Android e no Windows

O port está em `Nordeluna-iOS`: o nome da pasta é antigo, mas o APK atual é Android.
O plugin Nordeluna Online usa o relay Python em `server/relay.py`. O APK é o cliente;
o servidor roda separadamente. GitHub Actions gera o APK, mas não hospeda partidas.

## Testar agora no mesmo Wi-Fi

1. Instale a atualização do jogo nos dois aparelhos. No Windows use os dados atuais do jogo.
2. No PC, abra `Iniciar servidor Online.cmd`. A janela mostra os endereços locais disponíveis.
3. Se já houver um relay usando a porta 8765, mantenha o relay existente ou encerre-o normalmente
   antes de iniciar outro. Nunca substitua o banco de uma sessão de trocas em andamento.
4. Permita o acesso ao Python na rede privada se o Windows pedir. Ambos devem estar no mesmo Wi-Fi;
   redes de visitantes podem impedir a comunicação entre dispositivos.
5. Em cada jogo, abra **Online > Servidor** e informe `http://IP-DO-PC:8765`.
   Não use `127.0.0.1` no celular: esse endereço aponta para o próprio aparelho.
6. Salve o jogo para guardar o endereço. Um jogador cria a sala e compartilha o código de oito caracteres.

Fechar a janela ou desligar o PC encerra o acesso ao servidor. O banco local fica em
`.cache/nordeluna-online-server/relay.sqlite3`. A configuração HTTP permite o teste local;
para internet, use um endereço HTTPS.

## Hospedar na internet (Railway com volume persistente)

Este projeto já inclui `server/Dockerfile` e `server/start.py`. Para publicar:

1. Entre na sua conta Railway e crie um projeto a partir deste repositório GitHub.
2. Configure **Root Directory** como `/server`. O Dockerfile executa `python start.py`.
3. Anexe um **volume persistente** montado em `/data`.
4. Mantenha `DB_PATH=/data/relay.sqlite3` e `HOST=0.0.0.0`. O processo usa a variável
   `PORT` fornecida pelo host (ou 8765). Use apenas uma réplica com este banco SQLite.
5. Configure a verificação de saúde em `/health` e gere o domínio público HTTPS do serviço.
6. Abra `https://SEU-DOMINIO/health`. Deve responder JSON com `ok: true`, `protocol: 1`, `revision: 2`.
7. Em **Online > Servidor**, configure a mesma URL HTTPS nos dois clientes e salve o jogo.

Para deixar o endereço preenchido por padrão em futuras versões, altere `DEFAULT_SERVER`
em `Plugins/Nordeluna Online/001_Config.rb` no jogo, recompile os plugins e gere outro APK.
Configurar pelo menu já funciona sem recompilar. O servidor público não foi criado automaticamente:
é necessário escolher a conta/plano e conectar o repositório na plataforma.

Os volumes e o custo dependem do plano contratado. Consulte a documentação atual:
[volumes Railway](https://docs.railway.com/volumes) e
[domínios públicos](https://docs.railway.com/networking/public-networking).
Render também oferece discos em serviços pagos; o serviço gratuito não preserva o SQLite entre
reinícios, portanto não serve para guardar os recibos das trocas:
[discos Render](https://render.com/docs/disks) e [limitações gratuitas](https://render.com/docs/free).

## Banco de trocas e compatibilidade

Preserve o banco SQLite e faça backups usando a API de backup SQLite ou com o servidor parado.
Não copie só o `.sqlite3` de um servidor ativo ignorando seus arquivos WAL. Não troque o servidor
nem apague seu banco enquanto houver Pokémon reservados: o cliente depende dos recibos para
recuperar uma troca após uma queda. O APK não inclui o banco, tokens, logs ou testes do servidor.

Os dois clientes precisam usar os mesmos dados de espécies, golpes, tipos e plugins de batalha.
O plugin compara a identificação da versão e um checksum dos dados. Aumente `BUILD` no plugin
sempre que modificar as regras/dados e distribua a atualização nas duas plataformas.

O relay atual destina-se a testes amistosos. Batalhas e recuperação de trocas têm testes automatizados,
mas a validação final ainda exige duas pessoas jogando nos aparelhos, inclusive interrompendo a rede
durante uma troca. Hospedagem não acrescenta matchmaking, contas ou proteção competitiva.

## O aviso EventScriptError

`Interpreter`, linha 177, é onde Essentials relança uma falha de um comando de evento.
Não é a causa original. Pode envolver um recurso ausente, uma chamada de plugin ou um estado
inesperado no mapa. A captura antiga mostra só a classe porque Essentials guarda a explicação
no campo `event_message`, enquanto o diálogo nativo consultava `message`.

O preload Android agora expõe a explicação completa e grava `nordeluna-event-errors.log` na pasta
do jogo. **Configurações > Saves > Exportar relatório de erro** inclui esse log, quando
existir. O mapa, evento e erro original permitem localizar a causa sem adivinhar pela captura.
Conseguir reabrir o jogo não comprova que o evento esteja corrigido.
