@echo off
REM doc-reviewer - Wrapper packaging : spawn une fenetre cmd /k qui restera ouverte.
start "doc-reviewer package" cmd /k "%~dp0_package.bat"
