#!/usr/bin/env python3
"""
TG Lite — Мастер сборки
Автоматически собирает .exe (Windows) и/или .apk (Android)

Использование:
    python build.py          # полная сборка
    python build.py --exe    # только Windows EXE
    python build.py --apk    # только Android APK
    python build.py --install # только установка зависимостей
"""

import sys
import subprocess
import platform
import argparse
from pathlib import Path

ROOT = Path(__file__).parent


def run(cmd, **kw):
    print(f"\n▶ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kw)
    if result.returncode != 0:
        print(f"✗ Ошибка! Код: {result.returncode}")
        sys.exit(result.returncode)
    return result


def install_deps():
    print("\n═══ Установка зависимостей ═══")
    reqs = ROOT / "requirements.txt"
    run([sys.executable, "-m", "pip", "install", "-r", str(reqs)])


def build_exe():
    print("\n═══ Сборка Windows EXE ═══")
    try:
        import PyInstaller
    except ImportError:
        run([sys.executable, "-m", "pip", "install", "pyinstaller"])

    spec = ROOT / "tglite.spec"
    run([sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(spec)], cwd=ROOT)

    exe = ROOT / "dist" / "TGLite.exe"
    if exe.exists():
        print(f"\n✓ EXE собран: {exe}")
        _try_build_installer()
    else:
        print("\n✗ EXE не найден после сборки")


def _try_build_installer():
    print("\n═══ Попытка создания установщика NSIS ═══")
    nsi = ROOT / "installer" / "setup.nsi"
    # Пробуем найти makensis
    candidates = [
        "makensis",
        r"C:\Program Files (x86)\NSIS\makensis.exe",
        r"C:\Program Files\NSIS\makensis.exe",
    ]
    for makensis in candidates:
        try:
            result = subprocess.run([makensis, str(nsi)], capture_output=True)
            if result.returncode == 0:
                print(f"✓ Установщик создан в installer/")
                return
        except FileNotFoundError:
            continue
    print("⚠ NSIS не найден — установщик не создан.")
    print("  Скачайте NSIS: https://nsis.sourceforge.io")
    print(f"  Затем вручную: makensis {nsi}")


def build_apk():
    print("\n═══ Сборка Android APK ═══")
    # Установка buildozer если нет
    try:
        import buildozer  # noqa
    except ImportError:
        run([sys.executable, "-m", "pip", "install", "buildozer"])

    # Копируем main_mobile.py как main.py для buildozer
    mobile_src = ROOT / "src" / "main_mobile.py"
    main_copy  = ROOT / "main.py"
    main_copy.write_text(mobile_src.read_text())

    os_name = platform.system()
    if os_name == "Linux":
        run(["buildozer", "android", "debug"], cwd=ROOT)
        apk_dir = ROOT / ".buildozer" / "android" / "platform" / "build-armeabi-v7a" / "dists"
        print(f"\n✓ APK собран. Ищите в: {apk_dir}")
    elif os_name == "Windows":
        print("\n⚠ Для сборки APK на Windows используйте WSL2 или Docker:")
        print("  docker run -it --rm -v $(pwd):/app kivy/buildozer android debug")
        print("\nЛибо задействуйте GitHub Actions (ci.yml включён в проект).")
    elif os_name == "Darwin":
        run(["buildozer", "android", "debug"], cwd=ROOT)
    else:
        print(f"⚠ Неизвестная ОС: {os_name}")

    # Убираем копию
    if main_copy.exists():
        main_copy.unlink()


def main():
    parser = argparse.ArgumentParser(description="TG Lite Build System")
    parser.add_argument("--exe",     action="store_true", help="Собрать только EXE")
    parser.add_argument("--apk",     action="store_true", help="Собрать только APK")
    parser.add_argument("--install", action="store_true", help="Только установить зависимости")
    args = parser.parse_args()

    print("╔══════════════════════════════╗")
    print("║       TG Lite  Builder       ║")
    print("╚══════════════════════════════╝")
    print(f"  Python : {sys.version.split()[0]}")
    print(f"  OS     : {platform.system()} {platform.machine()}")
    print(f"  Root   : {ROOT}")

    if args.install:
        install_deps()
    elif args.exe:
        install_deps()
        build_exe()
    elif args.apk:
        install_deps()
        build_apk()
    else:
        install_deps()
        build_exe()
        if platform.system() != "Windows":
            build_apk()
        else:
            print("\n⚠ APK не собирается напрямую на Windows.")
            print("  Используйте: python build.py --apk  (требует WSL2 / Docker)")

    print("\n✓ Готово!")


if __name__ == "__main__":
    main()
