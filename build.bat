@echo off
REM ===========================================================
REM  Build script for WorksheetAgent.exe
REM  Produces: dist\WorksheetAgent.exe (single-file, windowed)
REM ===========================================================

setlocal

echo Checking for PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    if errorlevel 1 (
        echo.
        echo Failed to install PyInstaller. Aborting.
        pause
        exit /b 1
    )
)

echo.
echo Building WorksheetAgent.exe...
pyinstaller --clean --noconfirm gui.spec
if errorlevel 1 (
    echo.
    echo Build failed. See errors above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Build complete!
echo  Output: dist\WorksheetAgent.exe
echo.
echo  Tip: copy WorksheetAgent.exe next to your Worksheets
echo  folder ^(or anywhere you like^) and double-click to run.
echo ============================================================
echo.
pause
