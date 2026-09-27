# Nordeluna para iOS

Aplicativo pessoal de jogo único para iPhone e iPad. Ele inicia diretamente o projeto
Pokémon Essentials 21.1, usando o núcleo móvel do mkxp-z publicado pelo Empo.

## Requisitos

- iPhone ou iPad com iOS 26 ou superior.
- Um repositório **privado** no GitHub, por causa dos arquivos pessoais do jogo.
- Sideloadly, AltStore ou SideStore para assinar e instalar o IPA gerado.

## Preparar os arquivos no Windows

Na raiz deste projeto, execute:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\prepare-nordeluna-assets.ps1
```

O script copia apenas os diretórios necessários para execução, cria um ZIP e o divide
em partes menores que o limite individual do GitHub. O jogo original em Downloads não é
alterado.

## Compilar sem Mac

1. Crie um repositório privado vazio no GitHub.
2. Envie este projeto, incluindo a pasta `game-assets`.
3. Abra **Actions → Build Nordeluna IPA → Run workflow**.
4. Ao terminar, baixe o artefato `Nordeluna-unsigned-ipa`.
5. Extraia o ZIP do artefato e instale `Nordeluna-unsigned.ipa` com Sideloadly,
   AltStore ou SideStore.

O IPA é ad-hoc/sem assinatura pessoal. A ferramenta de sideload faz a assinatura com sua
conta Apple. Não coloque sua senha ou certificado em arquivos deste projeto.

## Dados e saves

Na primeira abertura, o aplicativo copia o jogo para o contêiner privado do iOS. Os saves
ficam em `Documentos/Nordeluna/Saves`, separados dos arquivos instalados e visíveis pelo
compartilhamento de arquivos do iOS.

## Licença

O launcher deriva do Empo/mkxp-z e permanece sob GPLv2+. O jogo e seus recursos não fazem
parte do código open source. Não publique o repositório com os arquivos do jogo.
