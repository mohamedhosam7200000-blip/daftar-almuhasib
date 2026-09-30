@echo off
rem Double-click to start Khabeer (offline AI assistant).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch.ps1"
if errorlevel 1 pause
