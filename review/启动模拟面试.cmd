@echo off
setlocal EnableExtensions
chcp 65001 >nul
rem 便携启动器：双击即用。首次运行自动安装 uv 并同步依赖（需联网，约 2 分钟）。
rem 之后每次启动秒开。无 API key 也可用（离线自评模式）。
cd /d "%~dp0.."

echo ============================================================
echo   AI Mock Interview Trainer  (comm-knowledge-graph)
echo ============================================================
echo   Browser will open at:  http://localhost:8501
echo   Works WITHOUT any API key (offline self-assessment mode).
echo   To enable the AI interviewer: paste a DeepSeek API key
echo   in the left sidebar of the app (stored locally only).
echo   Close this window (or Ctrl+C) to STOP.
echo ============================================================

where uv >nul 2>nul
if errorlevel 1 (
    echo [setup] uv not found, installing it first...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo [ERROR] Failed to install uv. Please install it manually: https://docs.astral.sh/uv/getting-started/installation/
        pause
        exit /b 1
    )
    rem uv 默认安装到 USERPROFILE\.local\bin，刷新当前会话 PATH
    set "PATH=%PATH%;%USERPROFILE%\.local\bin"
)

echo [1/2] Syncing dependencies ^(first run only^)...
uv sync
if errorlevel 1 (
    echo [ERROR] Dependency sync failed. Check your network or Python version ^(need 3.10+^).
    pause
    exit /b 1
)

echo [2/2] Starting Streamlit...
uv run streamlit run review/app.py

pause
