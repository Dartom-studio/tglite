[app]
title = TG Lite
package.name = tglite
package.domain = org.tglite
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 2.1.0
requirements = python3,kivy==2.3.0,telethon,pysocks,cryptg,pillow
orientation = portrait
android.permissions = INTERNET,ACCESS_NETWORK_STATE,VIBRATE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
log_level = 2

[buildozer]
log_level = 2
warn_on_root = 1
