@echo off
title Servidor Local - API de Historico de Vendas
cls
echo ======================================================================
echo  Iniciando API Local de Historico de Vendas na porta 8001...
echo  Documentacao Swagger: http://127.0.0.1:8001/docs
echo ======================================================================

set "API_EXE="
for %%P in (
    "%USERPROFILE%\Desktop\API_Historico_Vendas\API_Historico_Vendas\api_vendas.exe"
    "%USERPROFILE%\Desktop\API_Historico_Vendas\api_vendas.exe"
    "%USERPROFILE%\OneDrive\Desktop\API_Historico_Vendas\API_Historico_Vendas\api_vendas.exe"
    "%USERPROFILE%\OneDrive\Desktop\API_Historico_Vendas\api_vendas.exe"
    "%USERPROFILE%\Downloads\API_Historico_Vendas\API_Historico_Vendas\api_vendas.exe"
    "%USERPROFILE%\Downloads\API_Historico_Vendas\api_vendas.exe"
) do (
    if not defined API_EXE if exist %%P set "API_EXE=%%~P"
)

if not defined API_EXE (
    echo [ERRO] Executavel api_vendas.exe nao encontrado em:
    echo   - %%USERPROFILE%%\Desktop\API_Historico_Vendas
    echo   - %%USERPROFILE%%\OneDrive\Desktop\API_Historico_Vendas
    echo   - %%USERPROFILE%%\Downloads\API_Historico_Vendas
    pause
    exit /b 1
)

echo Executando: "%API_EXE%"
"%API_EXE%" --port 8001
pause
