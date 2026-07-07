@echo off
REM cati - Spawn une nouvelle console qui restera ouverte avec cmd /k.
REM Aucun accent dans ce fichier pour eviter les soucis de code page Windows.
start "cati" cmd /k "%~dp0_run.bat"
