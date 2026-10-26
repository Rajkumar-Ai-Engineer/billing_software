@echo off
setlocal enabledelayedexpansion
title SRI DHANAM MOTORS - Database Backup Tool
color 0B
cd /d "%~dp0"

echo ===============================================================================
echo       SRI DHANAM MOTORS - ONE-CLICK DATABASE BACKUP
echo ===============================================================================
echo.

:: Find database file
set "DB_FILE="
set "BACKUP_DIR="
if exist "sdm_billing\data\sdm.db" (
    set "DB_FILE=%~dp0sdm_billing\data\sdm.db"
    set "BACKUP_DIR=%~dp0backups"
) else if exist "my_billing_app\sdm_billing\data\sdm.db" (
    set "DB_FILE=%~dp0my_billing_app\sdm_billing\data\sdm.db"
    set "BACKUP_DIR=%~dp0my_billing_app\backups"
) else if exist "data\sdm.db" (
    set "DB_FILE=%~dp0data\sdm.db"
    set "BACKUP_DIR=%~dp0..\backups"
)

if "%DB_FILE%"=="" (
    color 0C
    echo [ERROR] Database file 'sdm.db' was not found.
    echo.
    pause
    exit /b 1
)

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set dt=%%I
if "%dt%"=="" (
    set "STAMP=%date:~-4,4%-%date:~-7,2%-%date:~-10,2%_%random%"
) else (
    set "STAMP=%dt:~0,4%-%dt:~4,2%-%dt:~6,2%_%dt:~8,2%-%dt:~10,2%"
)

set "DEST=%BACKUP_DIR%\sdm_backup_%STAMP%.db"

copy "%DB_FILE%" "%DEST%" >nul
if !errorlevel! equ 0 (
    echo [SUCCESS] Backup created successfully!
    echo.
    echo  - Source Database : %DB_FILE%
    echo  - Backup File     : %DEST%
    echo.
    echo Keep your backups safe on an external drive or cloud periodically.
) else (
    color 0C
    echo [ERROR] Failed to create database backup.
)
echo.
pause
