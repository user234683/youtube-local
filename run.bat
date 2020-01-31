@echo off

REM  https://stackoverflow.com/a/25719250
REM  setlocal makes sure changing directory only applies inside this bat file,
REM  and not in the command shell.
setlocal

REM  So this bat file can be called from a different working directory.
REM  %~dp0 is the directory with this bat file.
cd /d "%~dp0"

REM  This is so brotli and gevent search in the python directory for the
REM  visual studio c++ runtime dlls
set PATH=.\python;%PATH%

.\python\python.exe -I .\server.py
echo Press any key to quit...
PAUSE > nul
