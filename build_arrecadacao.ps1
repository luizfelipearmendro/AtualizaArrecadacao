# Gera o executavel do AtualizaArrecadacao.
# Uso:  powershell -ExecutionPolicy Bypass -File build_arrecadacao.ps1
#       powershell -ExecutionPolicy Bypass -File build_arrecadacao.ps1 -Empacotar
#
# Com -Empacotar, fecha um .zip nomeado com a versao, pronto para enviar.

param([switch]$Empacotar)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$nome = "AtualizaArrecadacao"

# A versao vem de casca/identidade.py, que e o unico lugar onde ela existe: o
# pe da barra lateral, o log de abertura e o nome do pacote saem todos dali.
# Assim nao ha como distribuir um zip "v1.1" com uma janela dizendo "v1.0".
$identidade = Join-Path $PSScriptRoot "casca\identidade.py"
$achado = Select-String -Path $identidade -Pattern 'APP_VERSAO\s*=\s*"([^"]+)"'
if (-not $achado) { throw "APP_VERSAO nao encontrada em casca\identidade.py." }
$versao = $achado.Matches[0].Groups[1].Value
Write-Host "Versao $versao (de casca\identidade.py)" -ForegroundColor Cyan

function Get-Identidade([string]$chave, [string]$reserva) {
    $m = Select-String -Path $identidade -Pattern "$chave\s*=\s*`"([^`"]+)`""
    if ($m) { return $m.Matches[0].Groups[1].Value }
    return $reserva
}
$empresa = Get-Identidade "APP_EMPRESA" "Agenda Assessoria"
$descricao = Get-Identidade "APP_DESCRICAO" "Atualiza Arrecadacao"
$produto = Get-Identidade "APP_NOME" "Atualiza Arrecadacao"

# Recurso de versao do executavel (aba Detalhes, no Windows). Sem ele o arquivo
# sai anonimo -- sem empresa, sem descricao, sem versao --, e binario anonimo e
# tratado com mais rigor pela heuristica de antivirus, alem de nao dizer nada a
# quem recebe o arquivo. O formato e um literal Python, avaliado pelo
# PyInstaller; 1046/1200 sao pt-BR e Unicode.
$partes = ($versao -split '\.') + @('0', '0', '0', '0')
$quadra = "{0}, {1}, {2}, {3}" -f $partes[0], $partes[1], $partes[2], $partes[3]
$conteudoVersao = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($quadra), prodvers=($quadra),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([StringTable('041604B0', [
      StringStruct('CompanyName', '$empresa'),
      StringStruct('FileDescription', '$descricao'),
      StringStruct('FileVersion', '$versao'),
      StringStruct('InternalName', '$nome'),
      StringStruct('OriginalFilename', '$nome.exe'),
      StringStruct('ProductName', '$produto'),
      StringStruct('ProductVersion', '$versao')])]),
    VarFileInfo([VarStruct('Translation', [1046, 1200])])
  ]
)
"@

# Pasta de trabalho FORA do repositorio: esta arvore fica no OneDrive, e pasta
# sincronizada trava arquivos no meio do build.
$trabalho = Join-Path $env:TEMP "$nome-build"
New-Item -ItemType Directory -Force $trabalho | Out-Null

# O recurso de versao mora no diretorio de trabalho, e nao no repositorio: ele
# e derivado de casca\identidade.py, e arquivo derivado versionado vira fonte
# de divergencia na primeira vez que alguem editar o lado errado.
$versaoArquivo = Join-Path $trabalho "versao_$nome.txt"
Set-Content -Path $versaoArquivo -Value $conteudoVersao -Encoding ASCII

$rodando = Get-Process -Name $nome -ErrorAction SilentlyContinue
if ($rodando) {
    Write-Host "Fechando $($rodando.Count) instancia(s) de $nome em execucao..." -ForegroundColor Yellow
    $rodando | Stop-Process -Force
    Start-Sleep -Seconds 2
}

# Nem toda maquina tem "python" no PATH: no Windows o nome costuma cair no
# atalho da Microsoft Store, que nao roda nada. O lancador "py" e o caminho
# confiavel quando isso acontece.
$python = "python"
try {
    $saida = & python --version 2>&1
    if ($LASTEXITCODE -ne 0 -or "$saida" -match "n.o foi encontrado|was not found") {
        $python = "py"
    }
} catch { $python = "py" }

Write-Host "Gerando $nome.exe ..." -ForegroundColor Cyan
Write-Host "  (interpretador: $python)" -ForegroundColor DarkGray
Write-Host "  (arquivos intermediarios em $trabalho)" -ForegroundColor DarkGray

# O tkinterdnd2 e OPCIONAL: sem ele o programa abre igual, so nao aceita
# arquivo arrastado. Mas `--collect-all` de um pacote ausente ABORTA o
# PyInstaller -- entao o build so pede o que existe, em vez de exigir a
# instalacao de algo que o programa nem precisa.
$argumentos = @(
    "--noconfirm", "--clean", "--onedir", "--windowed",
    "--name", $nome,
    "--workpath", $trabalho,
    "--specpath", $trabalho,
    "--icon", "$PSScriptRoot\assets\favicon.ico",
    "--version-file", "$versaoArquivo",
    "--noupx",
    "--collect-submodules", "casca",
    "--collect-submodules", "comum",
    "--collect-submodules", "arrecadacao",
    "--hidden-import", "openpyxl.cell._writer",
    "--add-data", "$PSScriptRoot\assets;assets",
    # Peso morto: nada disto e importado, e cada um leva dezenas de MB.
    "--exclude-module", "matplotlib",
    "--exclude-module", "scipy",
    "--exclude-module", "numpy",
    "--exclude-module", "pandas",
    "--exclude-module", "PyQt5",
    "--exclude-module", "PySide6",
    "--exclude-module", "IPython",
    "--exclude-module", "notebook",
    "--exclude-module", "torch",
    "--exclude-module", "langchain"
)

& $python -c "import tkinterdnd2" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  (arrastar e soltar: incluido)" -ForegroundColor DarkGray
    $argumentos += @("--collect-all", "tkinterdnd2")
} else {
    Write-Host "  (arrastar e soltar: tkinterdnd2 ausente, seguindo sem ele)" -ForegroundColor Yellow
}
$argumentos += "app_arrecadacao.py"

& $python -m PyInstaller @argumentos
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou." }

$pasta = Join-Path $PSScriptRoot "dist\$nome"
if (Test-Path "LEIAME.txt") { Copy-Item "LEIAME.txt" $pasta -Force }

$tamanho = [math]::Round(((Get-ChildItem $pasta -Recurse -File |
            Measure-Object -Property Length -Sum).Sum) / 1MB, 1)
Write-Host ""
Write-Host "Pronto: $pasta ($tamanho MB) -- versao $versao" -ForegroundColor Green

if ($Empacotar) {
    # O zip leva a versao no nome, e nao a data: quem recebe precisa saber
    # QUAL versao esta abrindo, e a data nao responde isso.
    $zip = Join-Path $PSScriptRoot "dist\${nome}_v$versao.zip"
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Write-Host "Compactando $zip ..." -ForegroundColor Cyan
    Compress-Archive -Path $pasta -DestinationPath $zip
    $mb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
    Write-Host "Pacote: $zip ($mb MB)" -ForegroundColor Green
}

Write-Host "Confira com:  $pasta\$nome.exe --autoteste" -ForegroundColor Cyan
Write-Host "Distribua a pasta dist\$nome\ inteira." -ForegroundColor Cyan
