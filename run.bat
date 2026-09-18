@echo off
rem Run PromptWizard on Windows without compiling anything.
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m promptwizard %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 -m promptwizard %*
) else (
  python -m promptwizard %*
)
