# Pokémon Nordeluna para Android

Port privado e de uso pessoal do Pokémon Nordeluna para Android, baseado no
motor `mkxp-z`. O aplicativo inclui um único jogo e é distribuído como APK
`arm64-v8a`.

## Estrutura

- `android/`: patches e recursos exclusivos do aplicativo Android;
- `game-assets/`: partes do arquivo privado do jogo;
- `scripts/prepare-nordeluna-assets.ps1`: recria as partes a partir da pasta
  original do jogo;
- `scripts/prepare-android-game.sh`: prepara os arquivos e áudios para o APK;
- `.github/workflows/nordeluna-android.yml`: gera o APK no GitHub Actions.

Consulte [NORDELUNA-ANDROID.md](NORDELUNA-ANDROID.md) para as instruções de
compilação e instalação.

## Licença

O código derivado do mkxp-z permanece sob GPLv2+. Os arquivos do jogo não
fazem parte do projeto upstream e destinam-se exclusivamente ao uso autorizado
do proprietário deste repositório privado.
