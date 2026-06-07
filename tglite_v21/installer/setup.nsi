; TG Lite v2.1 — NSIS Installer
; makensis installer\setup.nsi

!define APP_NAME    "TG Lite"
!define APP_VERSION "2.1.0"
!define REG_KEY     "Software\Microsoft\Windows\CurrentVersion\Uninstall\TGLite"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "TGLite_Setup_${APP_VERSION}.exe"
InstallDir "$PROGRAMFILES64\TGLite"
RequestExecutionLevel admin
SetCompressor /SOLID lzma

!include "MUI2.nsh"
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Russian"

Section "TG Lite" SecMain
    SectionIn RO
    SetOutPath "$INSTDIR"
    File "..\dist\TGLite.exe"
    File "..\dist\TGLiteUpdater.exe"
    CreateShortcut "$DESKTOP\TG Lite.lnk"         "$INSTDIR\TGLite.exe"
    CreateShortcut "$DESKTOP\TG Lite Updater.lnk" "$INSTDIR\TGLiteUpdater.exe"
    CreateDirectory "$SMPROGRAMS\TG Lite"
    CreateShortcut "$SMPROGRAMS\TG Lite\TG Lite.lnk"           "$INSTDIR\TGLite.exe"
    CreateShortcut "$SMPROGRAMS\TG Lite\TG Lite Updater.lnk"   "$INSTDIR\TGLiteUpdater.exe"
    CreateShortcut "$SMPROGRAMS\TG Lite\Удалить TG Lite.lnk"   "$INSTDIR\Uninstall.exe"
    WriteRegStr   HKLM "${REG_KEY}" "DisplayName"    "${APP_NAME}"
    WriteRegStr   HKLM "${REG_KEY}" "DisplayVersion" "${APP_VERSION}"
    WriteRegStr   HKLM "${REG_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Запустить TG Lite Updater при старте Windows" SecAutostart
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" \
        "TGLiteUpdater" "$INSTDIR\TGLiteUpdater.exe"
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\TGLite.exe"
    Delete "$INSTDIR\TGLiteUpdater.exe"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir  "$INSTDIR"
    Delete "$DESKTOP\TG Lite.lnk"
    Delete "$DESKTOP\TG Lite Updater.lnk"
    RMDir /r "$SMPROGRAMS\TG Lite"
    DeleteRegKey HKLM "${REG_KEY}"
    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "TGLiteUpdater"
SectionEnd
