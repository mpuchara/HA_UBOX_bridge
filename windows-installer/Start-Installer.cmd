@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-CYD.ps1"
if errorlevel 1 (
  echo Instalator nie zostal uruchomiony.
  pause
)
