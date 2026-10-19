@echo off
REM ===========================================================================
REM  image-replace - Generation du package partageable.
REM
REM  Wrapper fail-safe : spawn une fenetre cmd /k qui restera ouverte.
REM  La logique vit dans _package.bat (et delegue a scripts\package_image-replace.py).
REM
REM  Pour un nouveau POC :
REM   - Renomme _package.bat et scripts\package_image-replace.py en utilisant
REM     le nom du POC (snake_case pour le .py, slug pour le bat).
REM   - Adapte le nom de l'app et les sources dans le .py.
REM ===========================================================================
start "image-replace package" cmd /k "%~dp0_package.bat"
