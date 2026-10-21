!macro NSIS_HOOK_POSTINSTALL
  SetDetailsView show
  DetailPrint "Installing Python runtimes and Image Processor dependencies..."
  nsExec::ExecToLog '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "$INSTDIR\runtime\install-desktop-runtime.ps1"'
  Pop $0
  StrCmp $0 "0" image_processor_runtime_installed
  DetailPrint "Runtime installation failed with exit code $0."
  MessageBox MB_ICONSTOP|MB_OK "Setup could not install the Python dependencies. Check the Internet connection and run the installer again."
  Abort
image_processor_runtime_installed:
  DetailPrint "Dependencies are ready. Image Processor can run offline."
!macroend

!macro NSIS_HOOK_POSTUNINSTALL
  RMDir /r "$INSTDIR\runtime\python-ocr"
  RMDir /r "$INSTDIR\runtime\python-lama"
  RMDir /r "$INSTDIR\runtime\python-ocr.installing"
  RMDir /r "$INSTDIR\runtime\python-lama.installing"
  RMDir /r "$INSTDIR\runtime\python-ocr.previous"
  RMDir /r "$INSTDIR\runtime\python-lama.previous"
!macroend
