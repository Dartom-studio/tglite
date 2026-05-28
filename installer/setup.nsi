; TG Lite — NSIS installer script
; Требует NSIS 3.x (https://nsis.sourceforge.io)
; Использование:
;   makensis installer/setup.nsi

!define APP_NAME      "TG Lite"
!define APP_VERSION   "1.0.0"
!define APP_PUBLISHER "TG Lite Project"
!define APP_EXE       "TGLite.exe"
!define APP_DIR       "$PROGRAMFILES64\TGLite"
!define REG_KEY       "Software\Microsoft\Windows\CurrentVersion\Uninstall\TGLite"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "TGLite_Setup_${APP_VERSION}.exe"
InstallDir "${APP_DIR}"
InstallDirRegKey HKLM "${REG_KEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor /SOLID lzma

; --- UI ---
!include "MUI2.nsh"
!define MUI_ABORTWARNING
!define MUI_ICON "..\assets\icon.ico"

; Страницы установки
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Страницы удаления
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Язык
!insertmacro MUI_LANGUAGE "Russian"

; --- Секция установки ---
Section "Основная программа" SecMain
    SectionIn RO

    SetOutPath "$INSTDIR"
    File "..\dist\TGLite.exe"

    ; Ярлык на рабочий стол
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"

    ; Ярлык в меню Пуск
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\Удалить ${APP_NAME}.lnk" "$INSTDIR\Uninstall.exe"

    ; Запись в реестр для "Программы и компоненты"
    WriteRegStr HKLM "${REG_KEY}" "DisplayName"      "${APP_NAME}"
    WriteRegStr HKLM "${REG_KEY}" "DisplayVersion"   "${APP_VERSION}"
    WriteRegStr HKLM "${REG_KEY}" "Publisher"        "${APP_PUBLISHER}"
    WriteRegStr HKLM "${REG_KEY}" "InstallLocation"  "$INSTDIR"
    WriteRegStr HKLM "${REG_KEY}" "UninstallString"  "$INSTDIR\Uninstall.exe"
    WriteRegDWORD HKLM "${REG_KEY}" "NoModify"  1
    WriteRegDWORD HKLM "${REG_KEY}" "NoRepair"  1

    ; Создать деинсталлятор
    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

; --- Секция удаления ---
Section "Uninstall"
    Delete "$INSTDIR\${APP_EXE}"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir  "$INSTDIR"

    Delete "$DESKTOP\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\Удалить ${APP_NAME}.lnk"
    RMDir  "$SMPROGRAMS\${APP_NAME}"

    DeleteRegKey HKLM "${REG_KEY}"
SectionEnd
