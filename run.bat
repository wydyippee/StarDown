@echo off
rem Zero-install launcher: python run.bat list --user octocat
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo [!] Python 3.11+ required. Grab it from python.org & pause & exit /b 1)
python -c "import httpx, rich" 2>nul || python -m pip install -q httpx "rich>=13"
set PYTHONPATH=%~dp0
python -m stardown %*
