@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

title Sales Assistant - Workflow Runner

echo.
echo ============================================================
echo   Sales Assistant - Workflow Runner
echo ============================================================
echo.

REM --- Check for embedded python ---
set PYTHON_EXE=python\python.exe
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Embedded Python not found at %CD%\python\python.exe
    echo Please run setup.bat first.
    pause
    exit /b 1
)

set /p TARGET_USD="Enter target annual revenue in USD (e.g. 1200000): "

echo.
echo Running workflow with target: %TARGET_USD%
echo.

%PYTHON_EXE% workflow.py %TARGET_USD%

echo.
echo Workflow finished.
pause
