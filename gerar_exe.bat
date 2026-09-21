@echo off
rem ============================================================================
rem  Gera o AtualizaArrecadacao.exe. Para dar DUPLO CLIQUE -- e o motivo deste
rem  arquivo existir: o build de verdade e um .ps1, e o Windows abre .ps1 no
rem  Notepad em vez de executar. Aqui o .bat chama o PowerShell com a permissao
rem  certa, instala o que faltar, roda o autoteste e ESPERA no fim, para a
rem  janela nao fechar antes de alguem ler o resultado.
rem
rem  Uso:  duplo clique
rem        gerar_exe.bat -Empacotar     (fecha tambem o .zip com a versao)
rem ============================================================================
setlocal
cd /d "%~dp0"
title Gerar o AtualizaArrecadacao.exe

echo ============================================================
echo   Gerando o AtualizaArrecadacao.exe
echo ============================================================
echo.

rem Nem toda maquina tem "python" no PATH: no Windows o nome costuma cair no
rem atalho da Microsoft Store, que nao roda nada. O lancador "py" e o caminho
rem confiavel quando isso acontece.
set PYTHON=python
%PYTHON% --version >nul 2>&1
if errorlevel 1 set PYTHON=py
%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo Python nao encontrado nesta maquina.
    echo Instale de python.org e marque "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)
for /f "delims=" %%v in ('%PYTHON% --version 2^>^&1') do echo   interpretador: %%v ^(%PYTHON%^)

rem Instala so o que faltar: o PyInstaller e o unico que nao serve para rodar o
rem programa, so para empacota-lo.
%PYTHON% -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo   PyInstaller ausente: instalando o necessario...
    echo.
    %PYTHON% -m pip install -r requirements-dev.txt
    if errorlevel 1 (
        echo.
        echo A instalacao FALHOU. Sem internet, ou pip bloqueado?
        echo.
        pause
        exit /b 1
    )
)
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_arrecadacao.ps1" %*
if errorlevel 1 (
    echo.
    echo ============================================================
    echo   O BUILD FALHOU. A mensagem do erro esta acima.
    echo ============================================================
    echo.
    pause
    exit /b 1
)

rem O exe e --windowed: nao imprime nada e nao prende o terminal. O autoteste
rem escreve o resultado em autoteste.log, ao lado dele.
echo.
echo ============================================================
echo   Conferindo o executavel (autoteste)
echo ============================================================
echo.
pushd "dist\AtualizaArrecadacao"
del /q autoteste.log >nul 2>&1
start /wait "" "AtualizaArrecadacao.exe" --autoteste
if exist autoteste.log (type autoteste.log) else (echo O autoteste nao gerou log.)
popd

echo.
echo ============================================================
echo   Pronto. Distribua a pasta dist\AtualizaArrecadacao\ inteira.
echo ============================================================
echo.
pause
