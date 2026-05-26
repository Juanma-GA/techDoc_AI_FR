@echo off
REM ===========================================================================
REM  doc-writer - Generation du package partageable.
REM
REM  Produit apps\doc-writer\dist\doc-writer-vX.Y.Z-YYYYMMDD.zip pret a envoyer
REM  a un collegue. La logique vit dans scripts\package_doc_writer.py.
REM
REM  Pure ASCII (pas d'accent) pour eviter les soucis de code page Windows.
REM ===========================================================================
start "doc-writer package" cmd /k "%~dp0_package.bat"
