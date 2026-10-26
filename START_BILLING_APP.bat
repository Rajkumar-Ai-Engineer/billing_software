@echo off
setlocal enabledelayedexpansion
title SRI DHANAM MOTORS - Billing ^& Inventory Management
color 0A

:: Switch to script folder
cd /d "%~dp0"

echo ===============================================================================
echo       SRI DHANAM MOTORS - BILLING ^& INVENTORY MANAGEMENT SYSTEM
echo             Sales, Services ^& Spares ^| Mobirippatti, Harur
echo ===============================================================================
echo.

:: 1. Locate Application Folder
set "APP_DIR="
set "ROOT_DIR="
if exist "sdm_billing\main.py" (
    set "APP_DIR=%~dp0sdm_billing"
    set "ROOT_DIR=%~dp0"
) else if exist "my_billing_app\sdm_billing\main.py" (
    set "APP_DIR=%~dp0my_billing_app\sdm_billing"
    set "ROOT_DIR=%~dp0my_billing_app"
) else if exist "main.py" (
    set "APP_DIR=%~dp0"
    set "ROOT_DIR=%~dp0.."
)

if "%APP_DIR%"=="" (
    color 0C
    echo [ERROR] Could not find 'sdm_billing' application folder!
    echo Please make sure the folder structure is intact.
    echo.
    pause
    exit /b 1
)

:: 2. Locate Python executable
set "PYTHON_EXE="
if exist "%ROOT_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"
) else if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
) else if exist "%APP_DIR%\..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%APP_DIR%\..\.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=python"
    ) else (
        where py >nul 2>nul
        if !errorlevel! equ 0 (
            set "PYTHON_EXE=py -3"
        )
    )
)

if "%PYTHON_EXE%"=="" (
    color 0C
    echo [ERROR] Python is not installed on this system.
    echo.
    echo To run Sri Dhanam Motors Billing:
    echo 1. Download Python from: https://www.python.org/downloads/
    echo 2. During installation, CHECK the box: "Add python.exe to PATH"
    echo 3. Re-run this batch file.
    echo.
    pause
    exit /b 1
)

echo [OK] Python Engine : Found
echo [OK] App Directory : %APP_DIR%
echo.

:: 3. Change to application directory
cd /d "%APP_DIR%"

:: 4. Start Browser in Background after short delay
echo Starting Web Interface...
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8000"

echo.
echo ===============================================================================
echo  APPLICATION IS RUNNING!
echo ===============================================================================
echo  * Billing ^& Inventory URL : http://127.0.0.1:8000
echo  * Local PC Access         : http://localhost:8000
echo  * Network / Mobile Access : http://0.0.0.0:8000
echo  * Thermal Printer Support : TVS-E LP 46 (Ready)
echo.
echo  [IMPORTANT] Keep this window OPEN while using the software.
echo  To safely stop the application, press Ctrl + C or close this window.
echo ===============================================================================
echo.

"%PYTHON_EXE%" -m uvicorn main:app --host 0.0.0.0 --port 8000

pause
