#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
img2code — превращает картинку в код.

Режимы:
  b64    картинка -> строка base64 + готовые out.html и out.php
  svg    картинка -> out.svg (настоящая трассировка через vtracer, если он
         установлен; иначе встроенная SVG-мозаика на чистом Pillow)
  ascii  картинка -> out.txt из символов
  all    всё сразу

Примеры командной строки:
  python main.py --mode b64   -i foto.jpg -o out
  python main.py --mode svg   -i logo.png -o logo --colors 12 --cells 80
  python main.py --mode ascii -i foto.jpg -o art --width 120
  python main.py --mode all   -i foto.jpg -o result

Без аргументов открывается простое окно (на Android — приложение Kivy).
"""

import argparse
import base64
import io
import os
import sys

from PIL import Image, ImageOps

# ---------------------------------------------------------------- необязательное
try:  # HEIC/HEIF — фото с iPhone (на Android недоступно, там HEIC не читается)
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:
    pass

try:  # настоящая цветная векторная трассировка (ставится только на ПК)
    import vtracer
except Exception:
    vtracer = None

ASCII_CHARS = "@%#*+=-:. "

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>img2code</title>
<style>
  body {{ margin: 0; min-height: 100vh; display: grid; place-items: center;
         background: #111; color: #eee; font-family: system-ui, sans-serif; }}
  img {{ max-width: 96vw; max-height: 88vh; border-radius: 12px;
        box-shadow: 0 8px 30px rgba(0, 0, 0, .5); }}
</style>
</head>
<body>
<img src="data:{mime};base64,{b64}" alt="картинка">
</body>
</html>
"""

PHP_TEMPLATE = """<?php
declare(strict_types=1);

// Данные лежат рядом, в файле {data_name}
$b64  = trim((string) file_get_contents(__DIR__ . '/{data_name}'));
$mime = '{mime}';

echo '<img src="data:' . $mime . ';base64,' . $b64 . '" alt="{alt}">' . PHP_EOL;
"""


# ------------------------------------------------------------------- утилиты
def is_android():
    return ("ANDROID_ARGUMENT" in os.environ
            or "ANDROID_ROOT" in os.environ
            or hasattr(sys, "getandroidapilevel"))


def load_image(path, max_side=1200):
    """Открывает картинку любого формата. max_side=0 — не уменьшать."""
    img = Image.open(path)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    img.load()
    if max_side and max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    return img


# ------------------------------------------------------------------- base64
def img_to_base64(img, fmt="jpeg", quality=85):
    """Возвращает (строка_base64, mime)."""
    buf = io.BytesIO()
    fmt = (fmt or "jpeg").lower()
    if fmt == "png":
        img.convert("RGBA").save(buf, "PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii"), "image/png"
    if fmt == "webp":
        img.convert("RGB").save(buf, "WEBP", quality=quality, method=6)
        return base64.b64encode(buf.getvalue()).decode("ascii"), "image/webp"
    img.convert("RGB").save(buf, "JPEG", quality=quality, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii"), "image/jpeg"


def save_b64_bundle(img, base_path, fmt="jpeg", quality=85):
    """Делает три файла: .b64 (чистая строка), .html и .php."""
    b64, mime = img_to_base64(img, fmt, quality)
    made = []

    data_path = base_path + ".b64"
    with open(data_path, "w", encoding="ascii") as f:
        f.write(b64)
    made.append(data_path)

    html_path = base_path + ".html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(HTML_TEMPLATE.format(mime=mime, b64=b64))
    made.append(html_path)

    php_path = base_path + ".php"
    with open(php_path, "w", encoding="utf-8") as f:
        f.write(PHP_TEMPLATE.format(data_name=os.path.basename(data_path),
                                    mime=mime, alt="картинка из img2code"))
    made.append(php_path)
    return made


# ------------------------------------------------------------------- SVG
def svg_mosaic(img, colors=16, cells=64):
    """SVG из прямоугольников: работает везде, на чистом Pillow.

    colors=0 — без квантования; cells — сколько ячеек по длинной стороне.
    """
    base = img.convert("RGB")
    W, H = base.size
    step = max(1, max(W, H) // max(8, int(cells)))
    w, h = max(1, W // step), max(1, H // step)
    small = base.resize((w, h), Image.BOX)
    if colors and int(colors) > 1:
        small = small.quantize(colors=int(colors), method=Image.MEDIANCUT).convert("RGB")
    px = small.load()
    cw, ch = W / w, H / h

    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'viewBox="0 0 %d %d">' % (W, H, W, H)]
    for y in range(h):
        x = 0
        while x < w:
            r, g, b = px[x, y]
            x2 = x + 1
            while x2 < w and px[x2, y] == (r, g, b):
                x2 += 1
            out.append('<rect x="%g" y="%g" width="%g" height="%g" fill="#%02x%02x%02x"/>'
                       % (x * cw, y * ch, (x2 - x) * cw, ch, r, g, b))
            x = x2
    out.append("</svg>")
    return "\n".join(out)


def save_svg(img, base_path, src_path=None, colors=16, cells=64):
    out_path = base_path + ".svg"
    if vtracer is not None and src_path:
        try:
            vtracer.convert_image_to_svg_py(
                src_path, out_path, colormode="color", hierarchical="stacked",
                mode="spline", filter_speckle=4, color_precision=6,
                layer_difference=16, corner_threshold=60, length_threshold=4.0,
                max_iterations=10, splice_threshold=45, path_precision=3)
            return out_path
        except Exception:
            pass
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg_mosaic(img, colors, cells))
    return out_path


# ------------------------------------------------------------------- ASCII
def img_to_ascii(img, width=110):
    gray = img.convert("L")
    w = max(8, int(width))
    h = max(1, int(gray.height / gray.width * w * 0.5))  # 0.5 — символы выше, чем шире
    gray = gray.resize((w, h), Image.LANCZOS)
    px = gray.load()
    n = len(ASCII_CHARS) - 1
    return "\n".join("".join(ASCII_CHARS[px[x, y] * n // 255] for x in range(w))
                     for y in range(h))


# ------------------------------------------------------------------- CLI
def run_cli(args):
    img = load_image(args.input, args.max_side)
    base = args.output or os.path.splitext(args.input)[0] + "_code"
    modes = [args.mode] if args.mode != "all" else ["b64", "svg", "ascii"]
    made = []

    if "b64" in modes:
        made += save_b64_bundle(img, base, args.format, args.quality)
    if "svg" in modes:
        made.append(save_svg(img, base, args.input, args.colors, args.cells))
    if "ascii" in modes:
        p = base + ".txt"
        with open(p, "w", encoding="utf-8") as f:
            f.write(img_to_ascii(img, args.width))
        made.append(p)

    for m in made:
        print("готово: " + m)
    return made


# ------------------------------------------------------------------- окно Windows
def run_tk_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.title("img2code — картинка в код")
    root.geometry("640x470")
    root.minsize(520, 380)

    state = {"file": ""}
    file_var = tk.StringVar(value="Файл не выбран")
    out_var = tk.StringVar(value="")
    v_b64 = tk.BooleanVar(value=True)
    v_svg = tk.BooleanVar(value=True)
    v_ascii = tk.BooleanVar(value=False)

    top = tk.Frame(root, padx=12, pady=10)
    top.pack(fill="x")

    def pick():
        p = filedialog.askopenfilename(
            title="Выберите картинку",
            filetypes=[("Картинки",
                        "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff *.heic *.heif"),
                       ("Все файлы", "*.*")])
        if p:
            state["file"] = p
            file_var.set(os.path.basename(p))

    def pick_dir():
        d = filedialog.askdirectory(title="Куда сохранить")
        if d:
            out_var.set(d)

    def run_convert():
        if not state["file"]:
            messagebox.showwarning("img2code", "Сначала выберите картинку")
            return
        modes = []
        if v_b64.get():
            modes.append("b64")
        if v_svg.get():
            modes.append("svg")
        if v_ascii.get():
            modes.append("ascii")
        if not modes:
            messagebox.showwarning("img2code", "Отметьте хотя бы один режим")
            return

        log.delete("1.0", "end")
        out_dir = out_var.get() or os.path.dirname(state["file"]) or "."
        name = os.path.splitext(os.path.basename(state["file"]))[0]
        base = os.path.join(out_dir, name + "_code")
        try:
            img = load_image(state["file"], 1200)
            if "b64" in modes:
                for f in save_b64_bundle(img, base):
                    log.insert("end", "готово: %s\n" % f)
            if "svg" in modes:
                log.insert("end", "готово: %s\n" % save_svg(img, base, state["file"]))
            if "ascii" in modes:
                p = base + ".txt"
                with open(p, "w", encoding="utf-8") as f:
                    f.write(img_to_ascii(img, 110))
                log.insert("end", "готово: %s\n" % p)
        except Exception as e:
            log.insert("end", "ошибка: %s\n" % e)
        log.see("end")

    tk.Button(top, text="Выбрать картинку", command=pick).pack(side="left")
    tk.Label(top, textvariable=file_var, anchor="w").pack(side="left", padx=10)

    mid = tk.Frame(root, padx=12, pady=4)
    mid.pack(fill="x")
    tk.Checkbutton(mid, text="base64 → HTML/PHP", variable=v_b64).pack(side="left")
    tk.Checkbutton(mid, text="SVG", variable=v_svg).pack(side="left", padx=10)
    tk.Checkbutton(mid, text="ASCII", variable=v_ascii).pack(side="left")

    mid2 = tk.Frame(root, padx=12, pady=8)
    mid2.pack(fill="x")
    tk.Button(mid2, text="Папка сохранения", command=pick_dir).pack(side="left")
    tk.Label(mid2, textvariable=out_var, anchor="w").pack(side="left", padx=10)

    tk.Button(root, text="Превратить в код", height=2, command=run_convert).pack(fill="x", padx=12)

    log = tk.Text(root, height=12, wrap="none")
    log.pack(fill="both", expand=True, padx=12, pady=10)

    root.mainloop()


# ------------------------------------------------------------------- окно Android
def run_kivy_gui():
    from kivy.app import App
    from kivy.core.text import LabelBase
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.checkbox import CheckBox
    from kivy.uix.filechooser import FileChooserListView
    from kivy.uix.label import Label
    from kivy.uix.popup import Popup
    from kivy.uix.textinput import TextInput

    # кириллица: подставляем системный шрифт Android
    for font_path in ("/system/fonts/Roboto-Regular.ttf",
                      "/system/fonts/DroidSans.ttf",
                      "/system/fonts/NotoSans-Regular.ttf"):
        if os.path.exists(font_path):
            try:
                LabelBase.register(name="Roboto", fn_regular=font_path)
            except Exception:
                pass
            break

    def choose_out_dir():
        try:
            from android.storage import primary_external_storage_path
            d = os.path.join(primary_external_storage_path(), "Download", "img2code")
        except Exception:
            d = os.path.join(App.get_running_app().user_data_dir, "img2code")
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
        return d

    def start_dir():
        for p in ("/storage/emulated/0/Download", "/storage/emulated/0/Pictures",
                  "/storage/emulated/0/DCIM", os.path.expanduser("~")):
            if os.path.isdir(p):
                return p
        return "/"

    class Root(BoxLayout):
        def __init__(self, **kw):
            super().__init__(orientation="vertical", padding=8, spacing=8, **kw)
            self.src = ""

            self.name_lbl = Label(text="Файл не выбран", size_hint_y=None, height=34)
            self.add_widget(self.name_lbl)

            b_pick = Button(text="Выбрать картинку", size_hint_y=None, height=48)
            b_pick.bind(on_release=self.open_picker)
            self.add_widget(b_pick)

            row = BoxLayout(size_hint_y=None, height=42, spacing=4)
            self.cb = {}
            for key, title in (("b64", "base64 → HTML/PHP"), ("svg", "SVG"), ("ascii", "ASCII")):
                box = CheckBox(active=(key != "ascii"), size_hint_x=None, width=44)
                self.cb[key] = box
                row.add_widget(box)
                row.add_widget(Label(text=title, size_hint_x=None, width=170))
            self.add_widget(row)

            b_run = Button(text="Превратить в код", size_hint_y=None, height=54)
            b_run.bind(on_release=self.convert)
            self.add_widget(b_run)

            self.log = TextInput(readonly=True, font_size="13sp")
            self.add_widget(self.log)

        def open_picker(self, *_):
            content = BoxLayout(orientation="vertical", spacing=6)
            fc = FileChooserListView(
                path=start_dir(),
                filters=["*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.gif",
                         "*.tif", "*.tiff", "*.heic"])
            content.add_widget(fc)
            popup = Popup(title="Выберите картинку", content=content, size_hint=(0.96, 0.96))

            btns = BoxLayout(size_hint_y=None, height=48, spacing=6)

            def ok(*_):
                if fc.selection:
                    self.src = fc.selection[0]
                    self.name_lbl.text = os.path.basename(self.src)
                popup.dismiss()

            b_ok = Button(text="Открыть")
            b_ok.bind(on_release=ok)
            b_cancel = Button(text="Отмена")
            b_cancel.bind(on_release=lambda *_: popup.dismiss())
            btns.add_widget(b_ok)
            btns.add_widget(b_cancel)
            content.add_widget(btns)
            popup.open()

        def convert(self, *_):
            if not self.src:
                self.log.text = "Сначала выберите картинку"
                return
            out_dir = choose_out_dir()
            name = os.path.splitext(os.path.basename(self.src))[0]
            base = os.path.join(out_dir, name + "_code")
            try:
                img = load_image(self.src, 1200)
                lines = []
                if self.cb["b64"].active:
                    lines += ["готово: " + f for f in save_b64_bundle(img, base)]
                if self.cb["svg"].active:
                    lines.append("готово: " + save_svg(img, base, self.src))
                if self.cb["ascii"].active:
                    p = base + ".txt"
                    with open(p, "w", encoding="utf-8") as f:
                        f.write(img_to_ascii(img, 110))
                    lines.append("готово: " + p)
                self.log.text = "\n".join(lines) + "\n\nФайлы лежат в папке:\n" + out_dir
            except Exception as e:
                self.log.text = "ошибка: %s" % e

    class Img2CodeApp(App):
        title = "img2code"

        def build(self):
            return Root()

    Img2CodeApp().run()


# ------------------------------------------------------------------- запуск
def main():
    p = argparse.ArgumentParser(prog="img2code",
                               description="Картинка в код: base64, SVG, ASCII")
    p.add_argument("--mode", "-m", choices=["b64", "svg", "ascii", "all"],
                   help="что сделать")
    p.add_argument("--input", "-i", help="файл картинки")
    p.add_argument("--output", "-o", help="базовое имя выходных файлов (без расширения)")
    p.add_argument("--format", default="jpeg", choices=["jpeg", "png", "webp"],
                   help="формат для base64 (по умолчанию jpeg)")
    p.add_argument("--quality", type=int, default=85, help="качество JPEG/WEBP, 1-100")
    p.add_argument("--max-side", type=int, default=1200,
                   help="уменьшить картинку до этой стороны, 0 — не уменьшать")
    p.add_argument("--colors", type=int, default=16, help="число цветов в SVG, 0 — без квантования")
    p.add_argument("--cells", type=int, default=64, help="густота сетки SVG (ячеек по длинной стороне)")
    p.add_argument("--width", type=int, default=110, help="ширина ASCII в символах")
    args = p.parse_args()

    if args.mode:
        if not args.input:
            p.error("вместе с --mode нужен --input с файлом картинки")
        run_cli(args)
        return

    if is_android():
        run_kivy_gui()
        return

    try:
        import tkinter  # noqa: F401
        run_tk_gui()
    except Exception as e:
        try:
            run_kivy_gui()
        except Exception:
            print("Не удалось открыть окно (%s).\n"
                  "Запустите из командной строки, например:\n"
                  "  python main.py --mode all -i foto.jpg -o out" % e)
            sys.exit(1)


if __name__ == "__main__":
    main()
