@echo off
REM doc-reviewer - Spawn une nouvelle console qui restera ouverte avec cmd /k.
REM Aucun accent dans ce fichier pour eviter les soucis de code page Windows.
start "doc-reviewer" "%ComSpec%" /k "%~dp0_run.bat"
