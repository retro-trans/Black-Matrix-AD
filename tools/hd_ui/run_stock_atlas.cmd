@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_stock_atlas.ps1" -Visible %*
if errorlevel 1 pause
