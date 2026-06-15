@echo off
REM Register Jarvis.exe to start automatically when you log in.
set "EXE=%~dp0dist\Jarvis.exe"

if not exist "%EXE%" (
    echo Jarvis.exe not found. Run build_exe.bat first.
    exit /b 1
)

powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\Jarvis.lnk'); $s.TargetPath='%EXE%'; $s.WorkingDirectory='%~dp0'; $s.Save()"

echo Jarvis will now start automatically on login.
echo Starting it now...
start "" "%EXE%"
