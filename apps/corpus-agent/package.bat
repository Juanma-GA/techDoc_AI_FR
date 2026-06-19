@echo off
REM corpus-agent - Wrapper packaging : spawn une fenetre cmd /k qui restera ouverte.
start "corpus-agent package" cmd /k "%~dp0_package.bat"
