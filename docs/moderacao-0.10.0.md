# Moderação Nordeluna 0.10.0

A moderação usa **contas reais do servidor, identificadas pelo ID**. O nick ajuda a encontrar a pessoa e pode mudar; a permissão, a sanção e o histórico continuam associados ao mesmo ID. A lista mostra contas que já entraram no servidor. Antes de confirmar uma ação, confira o ID, o nick e o motivo na prévia.

## Dono e moderadores

| Papel | Acesso | Permissões |
| --- | --- | --- |
| Dono | **Painel Online Nordeluna.cmd**, aba **Moderação**, com seu token Discloud no campo mascarado | Consultar contas, chat e auditoria; aplicar sanções; escolher a conta do dono; conceder, renovar e revogar acesso de moderador. |
| Moderador | **Moderação Nordeluna.cmd**, com sua própria chave no campo **Chave de moderador** | Consultar contas, chat e auditoria; silenciar, expulsar da praça, banir/desbanir jogadores e ocultar/restaurar mensagens. |
| Jogador | Conta do jogo | Usar os recursos online conforme as permissões e sanções da conta. |

O token Discloud é exclusivo do dono e dá acesso administrativo à hospedagem. Não entregue esse token aos moderadores. O painel o mantém na memória da janela; não é necessário colocá-lo em arquivo, script ou pacote do jogo.

O dono escolhe sua conta explicitamente: na subaba **Contas**, localize o ID correto e use **Marcar como minha conta**. A primeira conta criada ou o primeiro nick encontrado não recebe esse papel automaticamente. A conta escolhida fica protegida contra sanções. Moderadores não podem gerenciar a equipe nem aplicar ações contra o dono ou outros moderadores.

Para delegar acesso, selecione a conta e use **Conceder / renovar chave**. A chave é mostrada uma vez em um diálogo mascarado, com opção de cópia, sem ser salva em arquivo. Entregue-a particularmente ao respectivo moderador. O servidor guarda somente o hash da chave. Renovar invalida a anterior; **Revogar moderador** bloqueia seu uso, inclusive em outra janela já aberta. Uma conta banida não pode usar sua chave de moderação.

O moderador abre sua janela, informa a chave e clica em **Entrar**. A validação ocorre por HTTPS. **Sair** encerra o acesso dessa janela. Cada moderador usa sua própria chave revogável. O pacote local `build/moderation/Moderacao-Nordeluna-0.10.0.zip` contém somente essa interface, sem jogo, banco ou token do Discloud; requer Python 3.10+ com Tkinter no Windows.

## Ações sobre jogadores

Na subaba **Contas**, busque pelo começo do nick ou do ID, selecione a conta e informe um motivo. A lista tem até 100 contas por página. As alterações exigem conferência da prévia antes da confirmação.

- **Silenciar:** duração de 1 a 120 minutos. O servidor impede novas mensagens da conta até o vencimento; o silêncio expira automaticamente, inclusive depois de reiniciar o servidor. **Retirar silêncio** encerra a restrição antecipadamente.
- **Expulsar da praça:** retira a conta da sala geral **PRACA** e impede o retorno durante **60 segundos**, inclusive por reconexão automática. Depois desse intervalo, o jogador pode voltar. A ação não apaga a conta.
- **Banir online:** bloqueia o acesso online da conta. O jogador mantém seu save e pode jogar offline. **Desbanir** libera novamente o acesso online; outras restrições ainda vigentes conservam seu próprio prazo.

As ações não apagam saves, Pokémon, inventário, moedas ou registros do banco. A recuperação de trocas já confirmadas (`committed`), presentes já resgatados e pedidos de loja já registrados permanece disponível para concluir entregas pendentes com segurança. Uma sanção não cancela nem paga novamente essas operações.

## Histórico e auditoria

**Histórico do chat** permite consultar mensagens por sala e conta, com paginação. O histórico passa a ser persistente a partir da instalação desta versão e sobrevive às reinicializações. Mensagens antigas que existiam somente na memória de versões anteriores não podem ser recuperadas retroativamente.

**Ocultar mensagem** remove a mensagem da exibição pública sem apagar o registro. Ela continua identificável no histórico administrativo, marcada como oculta. **Restaurar mensagem** volta a permitir sua exibição; o chat do jogo continua mostrando apenas sua janela de mensagens recentes.

**Auditoria** registra o responsável, a ação, a conta atingida, o motivo e a data. A concessão/revogação de equipe e a ocultação/restauração de mensagens também deixam registro. As datas e horas exibidas no painel usam **UTC−3**. A exportação CSV corresponde à página carregada.

## Instalação e preservação

O servidor e os plugins desta entrega são **0.10.0**, com servidor na **revisão 13**. O ZIP do Discloud inclui `moderation.py`; o atualizador exige esse arquivo na revisão 13 ou superior e continua reconhecendo o pacote de nove arquivos da revisão 12 para rollback. Não use rollback como forma de remover sanções: versões anteriores não oferecem as mesmas verificações.

A instalação acrescenta as tabelas `moderation_owner`, `moderators`, `moderation_sanctions`, `moderation_audit`, `chat_history` e `moderation_state` ao banco existente. O atualizador faz backup antes do envio e compara também as contagens dessas tabelas na verificação de preservação. O pacote contém código de servidor, sem incluir o banco em uso ou saves. Os fluxos anteriores de contas, trocas, presentes, Luna Coins, loja, conteúdo, testers e avisos continuam preservados.

Os aparelhos precisam receber um APK com os plugins 0.10.0 para os avisos e estados de moderação do cliente. Atualizar apenas o servidor não instala plugins no Android. O teste visual e o fluxo completo em **Android físico permanecem pendentes**. A atualização do Discloud usa a janela local de token, com backup e verificação do banco. O painel de moderação não envia alterações ao GitHub nem dispara build do APK.
