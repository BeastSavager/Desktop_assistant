@echo off
REM Build the single-file Jarvis.exe web app launcher.
echo Installing build dependencies...
python -m pip install -r requirements-dev.txt || goto :error

echo Building Jarvis.exe (this can take a few minutes)...
pyinstaller jarvis.spec --noconfirm || goto :error

echo.
echo Done. The app is at: dist\Jarvis.exe
echo Run install_startup.bat to launch it automatically on login.
goto :eof

:error
echo Build failed.
exit /b 1
