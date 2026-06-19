@echo off
REM ===========================================================================
REM  s1000d-extractor - Generation du package partageable.
REM
REM  Wrapper fail-safe : spawn une fenetre cmd /k qui restera ouverte.
REM  La logique vit dans _package.bat (et delegue a scripts\package_s1000d-extractor.py).
REM
REM  Pour un nouveau POC :
REM   - Renomme _package.bat et scripts\package_s1000d-extractor.py en utilisant
REM     le nom du POC (snake_case pour le .py, slug pour le bat).
REM   - Adapte le nom de l'app et les sources dans le .py.
REM ===========================================================================
start "s1000d-extractor package" cmd /k "%~dp0_package.bat"
