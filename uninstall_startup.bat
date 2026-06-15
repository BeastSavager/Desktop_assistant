@echo off
REM Remove Jarvis from auto-start.
powershell -NoProfile -Command ^
  "Remove-Item ([Environment]::GetFolderPath('Startup')+'\Jarvis.lnk') -ErrorAction SilentlyContinue"
echo Removed Jarvis auto-start. (Any running instance keeps running until you close it.)
