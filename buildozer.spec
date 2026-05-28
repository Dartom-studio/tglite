[app]
title = TG Lite
package.name = tglite
package.domain = org.tglite

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 1.0.0

requirements = python3,kivy==2.3.0,telethon,pysocks,cryptg,pillow

# Ориентация
orientation = portrait

# Иконка (можно заменить)
# icon.filename = assets/icon.png

# Presplash экран
# presplash.filename = assets/splash.png

# Android разрешения
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,VIBRATE

android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.private_storage = True
android.accept_sdk_license = True

android.archs = arm64-v8a, armeabi-v7a

# Логи
log_level = 2

[buildozer]
log_level = 2
warn_on_root = 1
