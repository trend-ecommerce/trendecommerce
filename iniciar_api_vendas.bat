@echo off
title Servidor Local - API de Historico de Vendas
cls
echo ======================================================================
echo  Iniciando API Local de Historico de Vendas na porta 8001...
echo  Documentacao Swagger: http://127.0.0.1:8001/docs
echo ======================================================================
"c:\Users\Aluno\Downloads\API_Historico_Vendas\API_Historico_Vendas\api_vendas.exe" --port 8001
pause
