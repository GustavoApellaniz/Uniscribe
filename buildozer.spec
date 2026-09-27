[app]
title = UniScribe
package.name = uniscribe
package.domain = app.uniscribe
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav
version = 0.1.0
requirements = python3,kivy
orientation = portrait
android.permissions = INTERNET,RECORD_AUDIO
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = false
android.accept_sdk_license = true

[buildozer]
log_level = 2
warn_on_root = 1
