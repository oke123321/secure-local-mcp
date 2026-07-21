@echo off
setlocal EnableDelayedExpansion

echo ========================================================
echo       Khoi dong Secure Local MCP Agent (NATIVE MODE)
echo ========================================================
echo.

:: 1. Tat Docker neu dang chay de tranh xung dot port 8501
echo [*] Dang tat Docker container...
docker compose down >nul 2>&1

:: 2. Kiem tra Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [!] Loi: Khong tim thay Python. Vui long cai dat Python 3.10+ va them vao PATH.
    pause
    exit /b
)

:: 3. Tao moi truong ao
if not exist "venv\" (
    echo [*] Dang tao moi truong ao venv...
    python -m venv venv
)

:: 4. Kich hoat va cai dat
echo [*] Dang kich hoat moi truong ao va cai dat thu vien...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt >nul 2>&1

:: 5. Thiet lap bien moi truong
set OLLAMA_HOST=http://localhost:11434
set NOTES_DIR=my_notes
if not exist "my_notes\" mkdir my_notes
if not exist "project_context\" mkdir project_context

:: 6. Chay
echo.
echo ========================================================
echo  [OK] He thong da san sang!
echo  [OK] Dang mo tai: http://localhost:8501
echo ========================================================
echo.
streamlit run src\ui.py
