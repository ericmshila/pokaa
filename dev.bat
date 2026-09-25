@echo off
REM Convenience launcher: starts BOTH the backend (FastAPI/uvicorn) and
REM the frontend (Vite) dev servers, each in its own window, so you
REM don't have to open two terminals and remember two commands every
REM time. Just double-click this file (or run it from any terminal).
REM
REM Closing a window (or Ctrl+C inside it) stops that one server —
REM the two are fully independent, same as running them by hand.

setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment not found at .venv\Scripts\python.exe
    echo.
    echo Set it up first:
    echo     python -m venv .venv
    echo     .venv\Scripts\pip install -r backend\requirements.txt
    echo.
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo [ERROR] frontend\node_modules not found.
    echo.
    echo Set it up first:
    echo     cd frontend
    echo     npm install
    echo.
    pause
    exit /b 1
)

echo Starting backend  (FastAPI)  on http://localhost:8000 ...
start "Kadi Backend"  cmd /k "cd /d "%~dp0" && .venv\Scripts\python.exe backend\run.py"

echo Starting frontend (Vite)     on http://localhost:5173 ...
start "Kadi Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo Both servers are launching in their own windows:
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173  (Vite will confirm the exact port)
echo.
echo This window can be closed - it only launched the other two.
