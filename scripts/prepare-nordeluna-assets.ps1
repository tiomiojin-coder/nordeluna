param(
    [string]$SourceGame = 'C:\Users\tiomi\Downloads\Pokémon Nordeluna\Pokemon Essentials v21.1 2023-07-30\Pokemon Essentials v21.1 2023-07-30',
    [int]$ChunkSizeMiB = 90
)

$ErrorActionPreference = 'Stop'
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$staging = [System.IO.Path]::GetFullPath((Join-Path $repoRoot '.game-pack-staging'))
$archive = [System.IO.Path]::GetFullPath((Join-Path $repoRoot 'game-assets.zip'))
$assetRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot 'game-assets'))

function Assert-ChildPath([string]$Path, [string]$Parent) {
    $prefix = $Parent.TrimEnd('\') + '\'
    if (-not $Path.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Caminho fora do projeto recusado: $Path"
    }
}

Assert-ChildPath $staging $repoRoot
Assert-ChildPath $archive $repoRoot
Assert-ChildPath $assetRoot $repoRoot

if (-not (Test-Path -LiteralPath (Join-Path $SourceGame 'Game.ini'))) {
    throw "Game.ini não encontrado em: $SourceGame"
}
if (-not (Test-Path -LiteralPath (Join-Path $SourceGame 'Data\Scripts.rxdata'))) {
    throw "Data\Scripts.rxdata não encontrado em: $SourceGame"
}

if (Test-Path -LiteralPath $staging) {
    Remove-Item -LiteralPath $staging -Recurse -Force
}
New-Item -ItemType Directory -Path $staging | Out-Null
New-Item -ItemType Directory -Force -Path $assetRoot | Out-Null

$runtimeDirectories = @('Audio', 'Data', 'Fonts', 'Graphics', 'Movies', 'Plugins')
foreach ($directory in $runtimeDirectories) {
    $source = Join-Path $SourceGame $directory
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $staging $directory) -Recurse
    }
}

# Ambiente Python usado por ferramentas de desenvolvimento do projeto. O Ruby
# do jogo nunca o carrega, e incluí-lo aumentaria desnecessariamente o APK.
$pythonVenv = [System.IO.Path]::GetFullPath((Join-Path $staging 'Plugins\.venv'))
Assert-ChildPath $pythonVenv $staging
if (Test-Path -LiteralPath $pythonVenv) {
    Remove-Item -LiteralPath $pythonVenv -Recurse -Force
}

$runtimeFiles = @('mkxp.json', 'soundfont.sf2', 'achievements.dat')
foreach ($file in $runtimeFiles) {
    $source = Join-Path $SourceGame $file
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $staging $file)
    }
}

$gameIni = [System.IO.File]::ReadAllText((Join-Path $SourceGame 'Game.ini'))
$gameIni = [System.Text.RegularExpressions.Regex]::Replace(
    $gameIni,
    '(?m)^Title=[^\r\n]*',
    'Title=Pokemon Nordeluna'
)
[System.IO.File]::WriteAllText(
    (Join-Path $staging 'Game.ini'),
    $gameIni,
    [System.Text.UTF8Encoding]::new($false)
)

if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
}
& tar.exe -a -cf $archive -C $staging .
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao criar game-assets.zip (tar retornou $LASTEXITCODE)."
}

& python (Join-Path $PSScriptRoot 'content-update-tools.py') --capture-apk $archive
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao registrar a base do atualizador de mapas."
}

Get-ChildItem -LiteralPath $assetRoot -Filter 'game-assets.zip.part*' -File |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }

$chunkBytes = [int64]$ChunkSizeMiB * 1MB
$input = [System.IO.File]::OpenRead($archive)
try {
    $buffer = New-Object byte[] (4MB)
    $part = 1
    while ($input.Position -lt $input.Length) {
        $partPath = Join-Path $assetRoot ('game-assets.zip.part{0:D3}' -f $part)
        $output = [System.IO.File]::Create($partPath)
        try {
            $written = [int64]0
            while ($written -lt $chunkBytes -and $input.Position -lt $input.Length) {
                $wanted = [int][Math]::Min($buffer.Length, $chunkBytes - $written)
                $read = $input.Read($buffer, 0, $wanted)
                if ($read -le 0) { break }
                $output.Write($buffer, 0, $read)
                $written += $read
            }
        } finally {
            $output.Dispose()
        }
        $part++
    }
} finally {
    $input.Dispose()
}

$hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText(
    (Join-Path $assetRoot 'sha256.txt'),
    "$hash  game-assets.zip`n",
    [System.Text.UTF8Encoding]::new($false)
)

$parts = Get-ChildItem -LiteralPath $assetRoot -Filter 'game-assets.zip.part*' -File | Sort-Object Name
$total = ($parts | Measure-Object Length -Sum).Sum
Write-Host "Pacote criado: $($parts.Count) partes, $total bytes"
Write-Host "SHA-256: $hash"

Remove-Item -LiteralPath $staging -Recurse -Force
Remove-Item -LiteralPath $archive -Force
