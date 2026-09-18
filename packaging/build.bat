@echo off
rem Build the standalone Windows executable: dist\promptwizard.exe
setlocal
cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=py -3"
)

echo Installing PyInstaller if needed...
%PY% -m pip install --upgrade --disable-pip-version-check pyinstaller || exit /b 1

echo Building...
%PY% -m PyInstaller --noconfirm --clean packaging\promptwizard.spec || exit /b 1

echo.
echo Built: dist\promptwizard.exe
