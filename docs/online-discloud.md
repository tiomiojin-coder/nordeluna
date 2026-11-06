# Publicar o servidor Nordeluna no Discloud

## Primeiro: reservar o subdomínio

No painel Discloud, abra **Domínios > Criar subdomínio**. Tente `nordeluna-online`
ou outro nome disponível. Use 2 a 20 caracteres, letras minúsculas, números e hífens.
O Discloud escolhe a terminação `.discloud.app` ou `.discloud.dev`; anote a URL real
mostrada no painel. O nome precisa estar reservado na sua conta antes do envio.

Sites/APIs exigem plano Platinum ou superior e pelo menos 512 MB segundo a documentação.
Se o painel solicitar uma assinatura, confira o plano antes de contratar.

## Preparar e enviar

Na raiz do port, gere o pacote com o nome que você reservou:

```powershell
python scripts/package-discloud.py --subdomain nordeluna-online
```

O ZIP fica em `build/discloud/nordeluna-online/Nordeluna-Online-Discloud.zip`.
Se escolher outro nome, substitua o argumento; o diretório de saída também muda.
O pacote tem apenas `discloud.config`, `main.py`, `relay.py` e `requirements.txt`
diretamente na raiz. O jogo, o APK, tokens, backups e bancos locais não vão junto.

Volte para **Aplicações > Nova aplicação > Upload ZIP**, clique para selecionar
e escolha esse arquivo. A configuração é:

- Tipo: Site/API (`TYPE=site`).
- Arquivo principal: `main.py`.
- RAM: 512 MB.
- Python: versão mais recente disponível, compatível com Python 3.10+.
- Rede: host `0.0.0.0`, porta `8080` (configurados no iniciador).
- ID: somente o nome reservado, sem `https://` ou a terminação do domínio.

Depois de iniciar, abra a URL real do painel acrescentando `/health`.
Exemplo ilustrativo: `https://nordeluna-online.discloud.app/health`.
O resultado esperado contém `ok: true`, `protocol: 1`, `revision: 2`.
Nos dois jogos, abra **Online > Servidor**, configure a mesma URL base **sem `/health`**
e salve o jogo. Não precisa gerar outro APK para configurar a URL pelo menu.

## Conferir o armazenamento antes das trocas

O banco será criado em `data/relay.sqlite3` dentro da aplicação. O ZIP de atualização
nunca contém esse arquivo nem a pasta `data`. Isso evita substituir o banco com um
arquivo vazio, mas não garante por si só que a hospedagem preserve os arquivos ao
recriar a aplicação.

Antes de usar Pokémon reais em trocas, confirme com o suporte/painel Discloud que
essa pasta é preservada nos reinícios **e** nas atualizações. Depois da primeira
inicialização, reinicie a aplicação: o log deve indicar `Banco local existente: sim`.
Repita a verificação ao atualizar a aplicação. Não exclua e recrie o serviço com
trocas pendentes. Faça backup consistente do SQLite com o servidor parado ou pela
API de backup SQLite; não copie apenas o arquivo principal enquanto o WAL está ativo.

Documentação oficial:
[subdomínios](https://docs.discloud.com/en/faq/general-questions/how-to-create-a-subdomain),
[sites e APIs](https://docs.discloud.com/en/how-to-host/websites-and-apis),
[configuração](https://docs.discloud.com/en/configurations/discloud.config).
