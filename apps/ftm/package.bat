@echo off
REM ftm - Wrapper packaging : spawn une fenetre cmd /k qui restera ouverte.
start "ftm package" cmd /k "%~dp0_package.bat"
