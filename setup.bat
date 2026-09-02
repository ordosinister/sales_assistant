@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

title Sales Assistant - Setup

echo.
echo ============================================================
echo   Sales Assistant - First-Time Setup
echo ============================================================
echo.

REM --- Check Python + pip ---
if exist "python\python.exe" (
    if exist "python\Scripts\pip.exe" (
        echo [OK] Embedded Python + pip already found.
        echo.
        goto :install_deps
    ) else (
        echo [WARN] python.exe found but pip is missing. Re-installing pip...
        goto :install_pip
    )
)

REM --- Download embedded Python ---
echo [DOWNLOAD] Python 3.14.7 embedded...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.14.7/python-3.14.7-embed-amd64.zip' -OutFile 'python_tmp.zip' -UseBasicParsing"
if errorlevel 1 (
    echo [ERROR] Download failed. Check internet connection.
    pause
    exit /b 1
)

REM --- Extract ---
echo [EXTRACT] Unpacking Python...
if not exist python mkdir python
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path 'python_tmp.zip' -DestinationPath 'python' -Force"
if errorlevel 1 (
    echo [ERROR] Extraction failed.
    pause
    exit /b 1
)

REM --- Enable pip ---
echo [CONFIG] Enabling pip support...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[System.IO.File]::WriteAllLines('python\python314._pth', @('python314.zip', '.', '', 'import site'), [System.Text.Encoding]::ASCII)"

REM --- Download get-pip.py ---
echo [DOWNLOAD] get-pip.py...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'python\get-pip.py' -UseBasicParsing"
if errorlevel 1 (
    echo [ERROR] Failed to download get-pip.py.
    pause
    exit /b 1
)

:install_pip
echo [INSTALL] pip...
python\python.exe python\get-pip.py
if errorlevel 1 (
    echo [ERROR] pip installation failed.
    pause
    exit /b 1
)

REM --- Cleanup ---
del python_tmp.zip >nul 2>&1
del python\get-pip.py >nul 2>&1

:install_deps
echo.
echo [INSTALL] Python packages from requirements.txt...
python\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Package installation failed.
    pause
    exit /b 1
)

echo [INSTALL] Chromium browser for Playwright...
python\python.exe -m playwright install chromium
if errorlevel 1 (
    echo [WARNING] Chromium browser install may have issues.
    echo           If report export fails, re-run setup.bat.
)

echo.
echo ============================================================
echo   SETUP COMPLETE
echo   Python: %CD%\python\python.exe
echo   You can now run: workflow.bat
echo ============================================================
echo.
pause
