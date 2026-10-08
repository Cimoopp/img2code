[app]

title = img2code
package.name = img2code
package.domain = org.cimoopp

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,ttf,webp

version = 1.0

# kivy — интерфейс, pillow — чтение картинок и конвертация
requirements = python3,kivy,pillow

orientation = portrait
fullscreen = 0

# доступ к картинкам в памяти телефона
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES

android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.accept_sdk_license = True

[buildozer]

log_level = 2
warn_on_root = 1
