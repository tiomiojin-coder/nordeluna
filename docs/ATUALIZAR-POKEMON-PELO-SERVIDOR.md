# Atualizar Pokémon pelo servidor

O atualizador ampliado distribui `Data/species.dat` e
`Data/species_metrics.dat` em pacotes assinados. O PBS original não é
enviado: ele precisa ser compilado no computador do autor primeiro.

## Preparação inicial

Distribua uma versão completa de PC e Android com Online 0.11.4 e os
launchers atualizados. Instale o servidor 0.10.4. Clientes anteriores não
recebem pacotes contendo essas tabelas; os novos clientes anunciam suporte.
Estas alterações foram preparadas localmente, sem publicação automática.

## Fluxo de publicação

1. Edite `PBS/pokemon.txt`, `pokemon_forms.txt` ou `pokemon_metrics.txt`.
2. Compile o projeto pelo modo de teste do Essentials. Se necessário,
   mantenha Ctrl pressionado durante a inicialização para forçar a compilação.
   Resolva os erros de compilação e feche o jogo antes de gerar o pacote.
3. No Painel Online, use a aba de pacotes de mapas e recursos para gerar o
   pacote cumulativo. A prévia identifica as tabelas de Pokémon alteradas.
4. Publique primeiro para testers e confira as alterações antes de liberar.
5. O jogador baixa a atualização pelo menu Online e fecha completamente o
   jogo. Ao reabrir, o pacote é aplicado com backup e recarga das tabelas.

O gerador confere referências a espécies, tipos, golpes, habilidades e
itens existentes. PBS mais recente que o compilado bloqueia a publicação.
Scripts e outras tabelas alteradas continuam exigindo atualização completa.
Não remova nem renomeie IDs existentes: o cliente recusa a remoção de
espécies/formas para preservar a compatibilidade com os saves.

Os pacotes conservam a assinatura do autor, hashes, limite de tamanho,
verificação da base instalada e restauração em caso de falha. Saves não
fazem parte do pacote. Jogadores em revisões de conteúdo diferentes são
barrados pelas verificações de compatibilidade online existentes.

A Central de Publicação também suporta tipos, golpes, habilidades, itens
e Pokédex regional compilados. Efeitos novos que precisam de código Ruby
e mudanças no motor continuam usando uma versão completa automática.
