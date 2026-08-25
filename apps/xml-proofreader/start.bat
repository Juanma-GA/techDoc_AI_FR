@echo off
REM XML Proofreader - Spawn une nouvelle console qui restera ouverte avec cmd /k.
REM Aucun accent dans ce fichier pour eviter les soucis de code page Windows.
start "XML Proofreader" cmd /k "%~dp0_run.bat"
