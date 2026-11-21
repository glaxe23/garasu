"""Запасные обои: рисует мягкий градиент, если при установке не удалось скачать обои из интернета.

  python fallback_wall.py <куда сохранить.png>"""
import sys
from PIL import Image, ImageDraw, ImageFilter

out = sys.argv[1]
W, H = 2560, 1440
im = Image.new("RGB", (W, H), (16, 20, 30))
d = ImageDraw.Draw(im)
for cx, cy, r, color in ((500, 300, 900, (58, 84, 122)), (2000, 1100, 1000, (120, 78, 110)),
                         (1500, 200, 700, (40, 96, 104)), (300, 1300, 700, (70, 58, 110))):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
im = im.filter(ImageFilter.GaussianBlur(260))
im.save(out)
