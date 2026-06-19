@echo off
REM s1000d-extractor - Spawn une nouvelle console qui restera ouverte avec cmd /k.
REM Aucun accent dans ce fichier pour eviter les soucis de code page Windows.
start "s1000d-extractor" cmd /k "%~dp0_run.bat"
