@echo off
cd /d "%~dp0"
rem Instala as dependencias que faltarem (so na primeira vez)
venv\Scripts\python.exe -c "import curl_cffi, python_calamine" 2>nul || venv\Scripts\python.exe -m pip install -q -r requirements.txt
venv\Scripts\python.exe atualizar_jogos.py %*
if errorlevel 1 (pause) else (timeout /t 10)
