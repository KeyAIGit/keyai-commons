@echo off
cd /d "%~dp0"
set "GOTOOL=go"
if exist "C:\KeyAI\Commons\toolchain\go\bin\go.exe" set "GOTOOL=C:\KeyAI\Commons\toolchain\go\bin\go.exe"
cd src
"%GOTOOL%" version
if errorlevel 1 goto failed
"%GOTOOL%" test ./...
if errorlevel 1 goto failed
"%GOTOOL%" build -trimpath -ldflags="-s -w" -o ..\KeyAI-Commons.exe .
if errorlevel 1 goto failed
cd ..
"%~dp0KeyAI-Commons.exe" demo
exit /b
:failed
echo Build failed. No training was started.
pause
