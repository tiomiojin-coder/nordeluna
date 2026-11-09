# Acesso de testers

No **Painel Online Nordeluna → Testers**, informe o token Discloud no campo mascarado, o nome do tester e validade de 1 a 365 dias. Clique em **Gerar chave**. A chave aparece uma vez, em um campo selecionável: envie somente ao destinatário.

O jogador instala o launcher estável público, seleciona **Testers** e usa **Atualizar**. O launcher pede o convite, resgata e guarda uma credencial privada. Depois baixa o pacote protegido, confere assinatura e hashes, descriptografa localmente e instala a versão de testes. No Android, a instalação exige confirmação do sistema. Ao usar **Jogar** no estável, a credencial é passada explicitamente ao aplicativo Testers.

O convite só é resgatado uma vez. Ele se vincula a um identificador aleatório desta instalação; não usa IMEI nem identificadores de hardware. Para PC e celular, gere dois convites. Reinstalar apagando os dados, remover o acesso local ou trocar de aparelho pode exigir outro convite. No Windows a credencial usa DPAPI por usuário; no Android fica nas preferências privadas. O token Discloud nunca é fornecido aos jogadores.

**Listar convites** mostra os acessos aguardando resgate, ativados, expirados ou revogados. **Revogar selecionado** bloqueia novas validações, downloads autorizados e requisições ao online de testes. Uma partida offline já em execução não é encerrada à força. O canal de testes exige internet na abertura e a revisão aprovada; o estável conserva o funcionamento offline.

## Publicar uma versão

1. Execute as builds PC/Android no mesmo commit. As builds usam AES-256-CBC com chave/IV aleatórios e envelopam a chave com a chave RSA pública do criador. Nenhum APK de testes em claro é publicado nos artefatos ou Releases.
2. Execute **Publicar atualizacao dos launchers.cmd**, com os tags/códigos apropriados quando mudarem. O finalizador verifica os assets do GitHub, abre a chave somente no computador do criador e assina o catálogo. O catálogo público contém apenas estável.
3. O finalizador gera `.cache/testers/publicacao-testers.json`. No painel Testers, use **Publicar versão protegida** para enviar esse arquivo ao servidor. Não compartilhe esse JSON: contém as chaves dos pacotes. Não vai para o Git.
4. Os testers com acesso ativo recebem a revisão aprovada pelo launcher. Os arquivos criptografados podem ficar no GitHub público; sozinhos não são um APK instalável. Isso evita transmitir centenas de MB pelo Discloud: o servidor só autentica e entrega alguns KB de metadados.

Os hashes do pacote cifrado estão no catálogo assinado e são conferidos antes de descriptografar; depois são conferidos tamanho e SHA-256 do conteúdo em claro. No Android o certificado do APK também é conferido. O servidor não guarda a chave RSA privada do criador.

## Limites e migração

O servidor precisa de `testers.py` e revisão 14. O pacote de deploy preserva o banco, incluindo convites e catálogo privado. A publicação no Discloud continua exigindo o token informado localmente.

O APK de testers 1.14 já foi distribuído publicamente. Retirar o asset e o catálogo antigo impede novos downloads por esses caminhos, mas não apaga cópias que alguém já guardou. Após atualizar o servidor, clientes antigos sem prova de acesso não entram no online de testes.

Esta é uma autorização de distribuição e do serviço online, não DRM absoluto. Uma pessoa com acesso ao aparelho, às credenciais ou ao código público pode copiar ou modificar o cliente. Nunca coloque segredos do servidor ou conteúdo que deva permanecer confidencial no repositório público.
