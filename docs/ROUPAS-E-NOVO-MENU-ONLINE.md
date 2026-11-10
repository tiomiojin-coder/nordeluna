# Menu Online e guarda-roupa

Implementação local: não publicada no GitHub nem no Discloud.

## O que está pronto

- Entrada Online com cartões Praça, Batalhas, Amigos e Loja. Setas, confirmação, voltar e toque funcionam; arrastar não confirma um cartão.
- Chat, conexão e menu Mais dão acesso às opções anteriores, incluindo presentes, missões, perfil e atualizações.
- Indicador verde conectado, amarelo conectando/reconectando e cinza offline. Selecione Conexão para detalhes; no painel compacto do chat, toque no indicador.
- Novidades nos launchers de PC e Android: imagem da marca, versão, até três destaques extraídos das notas e botão para ler tudo. O texto completo tem rolagem.
- Recompensa `outfit`: roupa comprada com Luna Coins, recibo recuperável, gravação no mesmo save da campanha e bloqueio de compras repetidas no servidor.
- O flashback e a perspectiva alternativa bloqueiam o Online e o guarda-roupa. A sessão da praça é encerrada antes da entrada na história paralela. A restauração original do Flashback System mantém personagem, roupa e charset do protagonista.

## Ainda não há roupas novas à venda

Não foram fornecidos sprites de roupas nem armário/loja no mapa. O catálogo começa vazio. O guarda-roupa oferece a roupa original; roupas compradas aparecerão quando forem cadastradas e entregues. Não criamos eventos em posições arbitrárias nem vendemos roupa sem arte.

## Criar o armário ou a loja da campanha

No RPG Maker XP, crie um evento no lugar desejado. Use **Action Button** e um comando **Script**:

```ruby
pbNordelunaWardrobe
```

O mesmo comando serve para armário, atendente ou provador. Não precisa estar conectado para vestir roupas já compradas. Salve a aventura após trocar; a roupa equipada acompanha o save. Não use evento em Auto Run.

## Cadastrar um traje quando os sprites existirem

Arquivo do jogo: `Plugins/Nordeluna Online/assets/outfits.json`.

Exemplo de cadastro (não é uma roupa incluída):

```json
{
  "LUNAR": {"name": "Traje lunar", "outfit": 1, "characters": [1]}
}
```

`characters` contém os IDs de protagonista em PlayerMetadata, não nomes de treinadores. `outfit` usa a convenção nativa do Essentials: para cada charset configurado no personagem, crie a variante com sufixo `_1`, por exemplo `trainer_PROTAGONIST_1.png`. Mantenha as dimensões e a grade 4×4 do arquivo original. São exigidas variantes de todos os movimentos configurados: andar, correr, bicicleta, surf, mergulho e pesca. Isso evita voltar à roupa antiga ao mudar de movimento. O sistema não recolore nem inventa os sprites.

Cadastre só IDs de protagonistas compatíveis; não inclua o professor. O ID `LUNAR` é permanente e aparece nos recibos: não reutilize para outra roupa nem remova uma roupa já vendida.

No **Painel Online Nordeluna → Loja**, escolha recompensa **Roupa** e o ID cadastrado, defina o preço e confira antes de publicar. O painel rejeita IDs ausentes do catálogo local; o cliente também verifica a arte antes de iniciar a compra. Não habilite o produto antes de distribuir o cliente e o servidor com esse suporte.

O cadastro JSON e o código do sistema exigem atualização completa pelo publicador atual. Depois disso, alterações nos PNGs de roupas já cadastradas podem usar os pacotes de recursos. Uma instalação nova do APK ainda exige confirmação do Android.

## Verificação

Testes de compra repetida e reinício do servidor; entrega da roupa e rollback por falha de save; navegação por setas/toque; bloqueio do transporte durante flashback e perspectiva; execução dos métodos reais `save_return_state` e `execute_finish` do Flashback System. Interface Android compilada; o teste visual em aparelho continua necessário antes de distribuir.
