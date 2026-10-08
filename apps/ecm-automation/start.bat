@echo off
REM ecm-rename - Spawn une nouvelle console qui restera ouverte avec cmd /k.
REM Aucun accent dans ce fichier pour eviter les soucis de code page Windows.
start "ecm-rename" cmd /k "%~dp0_run.bat"
