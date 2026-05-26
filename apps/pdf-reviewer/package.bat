@echo off
REM pdf-reviewer - Wrapper packaging : spawn une fenetre cmd /k qui restera ouverte.
start "pdf-reviewer package" cmd /k "%~dp0_package.bat"
