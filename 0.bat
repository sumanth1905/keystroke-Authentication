@echo off
cls
echo System is starting.... wait for a few seconds.
echo.

:: Kill explorer.exe
taskkill /IM explorer.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul

:: Start the VBScript file
start "" "wscript.exe" "%~dp0launcher.vbs"

:wait_for_lock
timeout /t 1 /nobreak >nul
if exist "%~dp0lockscreen.lock" (
    goto :restore_explorer
) else (
    goto :wait_for_lock
)

:restore_explorer
timeout /t 1 /nobreak >nul
start explorer.exe

:wait_explorer
timeout /t 1 /nobreak >nul
tasklist /FI "IMAGENAME eq explorer.exe" 2>NUL | find /I /N "explorer.exe">NUL
if "%ERRORLEVEL%"=="0" (
  goto :exit
) else (
  goto :wait_explorer
)

:exit
exit