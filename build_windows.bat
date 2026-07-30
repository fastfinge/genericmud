@echo off
REM Build a standalone dist\genericMud\genericMud.exe. Run this ON Windows
REM (PyInstaller does not cross-compile). Produces a windowed GUI app.
setlocal
cd /d "%~dp0"
where py >nul 2>nul && (set "PY=py") || (set "PY=python")
if not exist .venv\Scripts\python.exe %PY% -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -e ".[gui,voice,audio,package]"
pyinstaller --onedir --name genericMud --windowed ^
  --copy-metadata genericmud ^
  --add-data "frontend;frontend" ^
  --add-data "genericmud\config\keymaps;genericmud\config\keymaps" ^
  --collect-all webview ^
  --collect-all accessible_output2 ^
  --collect-all pygame ^
  --collect-all lupa --hidden-import websockets ^
  --hidden-import win32com.client --hidden-import pythoncom ^
  run_genericmud.py
echo.
echo Built: dist\genericMud\genericMud.exe
endlocal
