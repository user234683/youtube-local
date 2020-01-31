@echo off

REM  This is so brotli and gevent search in the python directory for the
REM  visual studio c++ runtime dlls
set PATH=.\python;%PATH%

.\python\python.exe -I .\server.py
echo Press any key to quit...
PAUSE > nul
