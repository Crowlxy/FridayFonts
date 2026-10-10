@echo off
setlocal
set "FF=%~dp0..\work\font-tools\fontforge"
set "PYTHONHOME=%FF%"
set "PYTHONPATH=%FF%\lib\python3.12"
set "PATH=%FF%\bin;%PATH%"
set "APPDATA=%~dp0..\work\font-tools\appdata"
"%FF%\bin\fontforge.exe" %*
exit /b %ERRORLEVEL%
